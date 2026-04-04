import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models.lookup import LookupValue

DRYSUIT_LOOKUPS = {
    'material_type': [
        ('Trilaminate', 'Trilaminate'),
        ('Neoprene', 'Neoprene'),
        ('Crushed Neoprene', 'Crushed Neoprene'),
        ('Cordura', 'Cordura'),
    ],
    'suit_entry_type': [
        ('Front Entry', 'Front Entry'),
        ('Rear Entry', 'Rear Entry'),
    ],
    'neck_seal_type': [
        ('Latex', 'Latex'),
        ('Silicone', 'Silicone'),
        ('Neoprene', 'Neoprene'),
    ],
    'wrist_seal_type': [
        ('Latex', 'Latex'),
        ('Silicone', 'Silicone'),
        ('Neoprene', 'Neoprene'),
    ],
    'zipper_type': [
        ('Metal', 'Metal'),
        ('Plastic (YKK ProSeal)', 'Plastic (YKK ProSeal)'),
    ],
    'boot_type': [
        ('Neoprene Boot', 'Neoprene Boot'),
        ('Turbo Sole', 'Turbo Sole'),
        ('Tech Boot', 'Tech Boot'),
        ('Integrated Sock', 'Integrated Sock'),
        ('Attached', 'Attached'),
    ]
}

@click.command('seed-lookups')
@with_appcontext
def seed_lookups_command():
    """Seed the lookup_values table with drysuit constants."""
    count = 0
    for category, pairs in DRYSUIT_LOOKUPS.items():
        for value, display_name in pairs:
            existing = LookupValue.query.filter_by(category=category, value=value).first()
            if not existing:
                lv = LookupValue(
                    category=category,
                    value=value,
                    display_name=display_name
                )
                db.session.add(lv)
                count += 1
    
    db.session.commit()
    click.echo(f"Seeded {count} lookup values.")

def init_app(app):
    app.cli.add_command(seed_lookups_command)
