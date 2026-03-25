# Documentation Screenshots

This directory contains the screenshots referenced by `docs/user_guide.md`.
They are captured from the live application using the Playwright snapshot lane
in `scripts/capture_docs_screenshots.py`.

## Assets

- `customer_detail.png` - customer detail page with contact information,
  service items, open orders, order history, and quick actions.
- `item_detail_service_history.png` - service item detail page with the item
  summary, attachment gallery, and service history.

## Regeneration

Start the UAT database and web container, then run the capture script inside
the UAT runner container:

```bash
docker compose -f docker-compose.uat.yml up -d web db
docker compose -f docker-compose.uat.yml run --rm uat \
  python scripts/capture_docs_screenshots.py
```

The runner writes directly into this directory, so re-running the command
overwrites the tracked PNGs with a fresh snapshot.
