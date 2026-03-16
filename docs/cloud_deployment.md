# Cloud Deployment Guide

This document provides deployment examples for running Dive Service Management
on major cloud platforms. Each section covers the compute service, managed
database, Redis cache, secret management, and health check configuration.

## Table of Contents

- [Health Check Endpoints](#health-check-endpoints)
- [Environment Variables for Cloud](#environment-variables-for-cloud)
- [AWS ECS/Fargate](#aws-ecsfargate)
- [GCP Cloud Run](#gcp-cloud-run)
- [Azure Container Apps](#azure-container-apps)
- [Object Storage for Uploads](#object-storage-for-uploads)

---

## Health Check Endpoints

The application exposes three health endpoints:

| Endpoint        | Purpose          | Checks           | Use For                    |
|-----------------|------------------|-------------------|----------------------------|
| `/health`       | General health   | Database           | Basic monitoring           |
| `/health/ready` | Readiness probe  | Database + Redis   | Load balancer target group |
| `/health/live`  | Liveness probe   | None (always 200)  | Container restart policy   |

Configure your load balancer or orchestrator to use `/health/ready` for routing
traffic and `/health/live` for restart decisions.

---

## Environment Variables for Cloud

In addition to the standard variables documented in `configuration.md`, cloud
deployments should set:

| Variable               | Description                              | Default |
|------------------------|------------------------------------------|---------|
| `DSM_FORCE_HTTPS`      | Redirect HTTP to HTTPS                   | `false` |
| `DSM_ALLOWED_HOSTS`    | Comma-separated allowed Host headers     | `*`     |
| `DSM_TRUSTED_PROXIES`  | Trusted proxy IPs for X-Forwarded-For    | (empty) |
| `DSM_STORAGE_BACKEND`  | Upload storage backend (future)          | `local` |

All `DSM_*` secrets (SECRET_KEY, passwords) should be injected from your
cloud provider's secret manager rather than stored in plaintext.

---

## AWS ECS/Fargate

### Task Definition

```json
{
  "family": "dsm-web",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/dsmTaskRole",
  "containerDefinitions": [
    {
      "name": "dsm-web",
      "image": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/dsm-web:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health/live || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 15
      },
      "secrets": [
        {
          "name": "DSM_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:dsm/secret-key"
        },
        {
          "name": "DSM_SECURITY_PASSWORD_SALT",
          "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:dsm/password-salt"
        },
        {
          "name": "MARIADB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:dsm/db-password"
        },
        {
          "name": "MARIADB_ROOT_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:dsm/db-root-password"
        }
      ],
      "environment": [
        {"name": "DSM_ENV", "value": "production"},
        {"name": "DSM_DATABASE_URL", "value": "mysql+mysqldb://dsm:PASSWORD@dsm-db.CLUSTER.REGION.rds.amazonaws.com:3306/dsm?charset=utf8mb4"},
        {"name": "DSM_REDIS_URL", "value": "redis://dsm-cache.CLUSTER.cache.amazonaws.com:6379/0"},
        {"name": "DSM_CELERY_BROKER_URL", "value": "redis://dsm-cache.CLUSTER.cache.amazonaws.com:6379/1"},
        {"name": "DSM_CELERY_RESULT_BACKEND", "value": "redis://dsm-cache.CLUSTER.cache.amazonaws.com:6379/2"},
        {"name": "DSM_FORCE_HTTPS", "value": "true"},
        {"name": "DSM_WORKERS", "value": "2"},
        {"name": "DSM_LOG_LEVEL", "value": "INFO"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/dsm-web",
          "awslogs-region": "REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### ALB Target Group Health Check

Configure the Application Load Balancer target group:

- **Health check path**: `/health/ready`
- **Protocol**: HTTP
- **Port**: 8080
- **Healthy threshold**: 2
- **Unhealthy threshold**: 3
- **Timeout**: 5 seconds
- **Interval**: 30 seconds
- **Success codes**: 200

### RDS MariaDB Provisioning

1. Create an RDS instance with engine **MariaDB 11.x**.
2. Choose instance class (e.g., `db.t3.micro` for development, `db.r6g.large` for production).
3. Enable **Multi-AZ** for production workloads.
4. Set the database name to `dsm`, master username to `dsm`.
5. Store the password in AWS Secrets Manager.
6. Configure the security group to allow inbound 3306 from the ECS task security group.
7. Set `DSM_DATABASE_URL` to:
   ```
   mysql+mysqldb://dsm:PASSWORD@your-rds-endpoint.REGION.rds.amazonaws.com:3306/dsm?charset=utf8mb4
   ```

### ElastiCache Redis

1. Create an ElastiCache Redis cluster (engine 7.x, node type `cache.t3.micro`).
2. Enable encryption in transit if connecting from Fargate.
3. Configure the security group to allow inbound 6379 from the ECS task security group.
4. Set `DSM_REDIS_URL`, `DSM_CELERY_BROKER_URL`, and `DSM_CELERY_RESULT_BACKEND` using the
   primary endpoint (use different database numbers: `/0`, `/1`, `/2`).

---

## GCP Cloud Run

### Service YAML

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: dsm-web
  annotations:
    run.googleapis.com/launch-stage: GA
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "4"
        run.googleapis.com/cloudsql-instances: "PROJECT:REGION:dsm-db"
    spec:
      serviceAccountName: dsm-sa@PROJECT.iam.gserviceaccount.com
      containers:
        - image: REGION-docker.pkg.dev/PROJECT/dsm/dsm-web:latest
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "1"
              memory: 1Gi
          startupProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 10
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
            periodSeconds: 30
          env:
            - name: DSM_ENV
              value: production
            - name: DSM_FORCE_HTTPS
              value: "true"
            - name: DSM_WORKERS
              value: "2"
            - name: DSM_LOG_LEVEL
              value: INFO
            - name: DSM_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: dsm-database-url
                  key: latest
            - name: DSM_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: dsm-secret-key
                  key: latest
            - name: DSM_SECURITY_PASSWORD_SALT
              valueFrom:
                secretKeyRef:
                  name: dsm-password-salt
                  key: latest
            - name: DSM_REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: dsm-redis-url
                  key: latest
```

### Cloud SQL Connection

1. Create a Cloud SQL instance with **MariaDB 11**.
2. Create a database `dsm` and user `dsm`.
3. Enable the Cloud SQL Auth Proxy or use the built-in Cloud Run connector
   (annotate the service with `run.googleapis.com/cloudsql-instances`).
4. The database URL uses a Unix socket:
   ```
   mysql+mysqldb://dsm:PASSWORD@/dsm?unix_socket=/cloudsql/PROJECT:REGION:dsm-db&charset=utf8mb4
   ```
5. Store credentials in Google Secret Manager and reference them in the service YAML.

### Memorystore Redis

1. Create a Memorystore for Redis instance (version 7.x, 1 GB).
2. Create a VPC connector so Cloud Run can reach the private IP.
3. Set `DSM_REDIS_URL=redis://MEMORYSTORE_IP:6379/0`.
4. Use separate database numbers for Celery broker (`/1`) and result backend (`/2`).

Note: Cloud Run is serverless and does not support long-running Celery workers.
Deploy Celery worker and beat containers on **GKE** or **Compute Engine** using
the same container image with a different entrypoint command.

---

## Azure Container Apps

### Container App Configuration

```json
{
  "properties": {
    "configuration": {
      "ingress": {
        "external": true,
        "targetPort": 8080,
        "transport": "auto"
      },
      "secrets": [
        {"name": "dsm-secret-key", "value": "REFERENCE_TO_KEY_VAULT"},
        {"name": "dsm-password-salt", "value": "REFERENCE_TO_KEY_VAULT"},
        {"name": "dsm-database-url", "value": "REFERENCE_TO_KEY_VAULT"},
        {"name": "dsm-redis-url", "value": "REFERENCE_TO_KEY_VAULT"}
      ]
    },
    "template": {
      "containers": [
        {
          "name": "dsm-web",
          "image": "youracr.azurecr.io/dsm-web:latest",
          "resources": {
            "cpu": 0.5,
            "memory": "1Gi"
          },
          "env": [
            {"name": "DSM_ENV", "value": "production"},
            {"name": "DSM_FORCE_HTTPS", "value": "true"},
            {"name": "DSM_WORKERS", "value": "2"},
            {"name": "DSM_LOG_LEVEL", "value": "INFO"},
            {"name": "DSM_SECRET_KEY", "secretRef": "dsm-secret-key"},
            {"name": "DSM_SECURITY_PASSWORD_SALT", "secretRef": "dsm-password-salt"},
            {"name": "DSM_DATABASE_URL", "secretRef": "dsm-database-url"},
            {"name": "DSM_REDIS_URL", "secretRef": "dsm-redis-url"}
          ],
          "probes": [
            {
              "type": "startup",
              "httpGet": {"path": "/health/ready", "port": 8080},
              "initialDelaySeconds": 5,
              "periodSeconds": 5,
              "failureThreshold": 10
            },
            {
              "type": "liveness",
              "httpGet": {"path": "/health/live", "port": 8080},
              "periodSeconds": 30
            },
            {
              "type": "readiness",
              "httpGet": {"path": "/health/ready", "port": 8080},
              "periodSeconds": 10
            }
          ]
        }
      ],
      "scale": {
        "minReplicas": 1,
        "maxReplicas": 4
      }
    }
  }
}
```

### Azure Database for MariaDB

1. Create an **Azure Database for MariaDB** flexible server.
2. Choose a compute tier appropriate for your workload (Burstable B1ms for dev,
   General Purpose D2ds_v4 for production).
3. Create database `dsm` and user `dsm`.
4. Enable SSL enforcement and download the CA certificate.
5. Allow connections from the Container Apps subnet.
6. Set `DSM_DATABASE_URL` to:
   ```
   mysql+mysqldb://dsm:PASSWORD@your-server.mariadb.database.azure.com:3306/dsm?charset=utf8mb4&ssl=true
   ```

### Azure Cache for Redis

1. Create an **Azure Cache for Redis** instance (Basic C0 for dev, Standard C1 for production).
2. Enable non-SSL port or configure the app to use `rediss://` for TLS.
3. Set `DSM_REDIS_URL=rediss://:ACCESS_KEY@your-cache.redis.cache.windows.net:6380/0`.
4. Use separate database numbers for Celery broker and result backend.

### Azure Key Vault

Store all secrets in Key Vault and reference them in the Container App configuration:

1. Create a Key Vault and add secrets: `dsm-secret-key`, `dsm-password-salt`,
   `dsm-database-url`, `dsm-redis-url`, `mariadb-password`.
2. Enable system-assigned managed identity on the Container App.
3. Grant the identity **Key Vault Secrets User** role.
4. Reference secrets in the container app config using Key Vault URIs.

---

## Object Storage for Uploads

The application currently stores file uploads on the local filesystem
(`DSM_UPLOAD_FOLDER`). For cloud deployments, a future release will add
support for cloud object storage via the `DSM_STORAGE_BACKEND` variable.

Planned storage backends:

| Provider | Service               | Variable Example                                     |
|----------|-----------------------|------------------------------------------------------|
| AWS      | S3                    | `DSM_STORAGE_BACKEND=s3` / `DSM_S3_BUCKET=dsm-uploads` |
| GCP      | Cloud Storage         | `DSM_STORAGE_BACKEND=gcs` / `DSM_GCS_BUCKET=dsm-uploads` |
| Azure    | Blob Storage          | `DSM_STORAGE_BACKEND=azure` / `DSM_AZURE_CONTAINER=dsm-uploads` |

Until cloud storage is implemented, use a persistent volume or shared
filesystem mount for the `/app/uploads` directory:

- **AWS ECS**: Use an EFS volume mounted at `/app/uploads`.
- **GCP Cloud Run**: Use a Cloud Storage FUSE sidecar or GCS volume mount.
- **Azure Container Apps**: Use an Azure Files volume mount.
