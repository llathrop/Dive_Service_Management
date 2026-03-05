"""Service note forms.

WTForms form class for adding notes to a service order item.
Notes support multiple types to categorize diagnostic findings,
repair actions, testing results, and customer communications.
"""

from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length


class ServiceNoteForm(FlaskForm):
    """Form for adding a note to a service order item.

    Notes are categorized by type so technicians and front-desk staff
    can quickly filter relevant information during the service workflow.
    """

    note_text = TextAreaField(
        "Note",
        validators=[DataRequired(), Length(min=1, max=10000)],
    )
    note_type = SelectField(
        "Note Type",
        choices=[
            ("general", "General"),
            ("diagnostic", "Diagnostic"),
            ("repair", "Repair"),
            ("testing", "Testing"),
            ("customer_communication", "Customer Communication"),
        ],
        default="general",
    )
    submit = SubmitField("Add Note")
