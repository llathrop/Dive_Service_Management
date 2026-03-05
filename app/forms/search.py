"""Global search forms.

A lightweight form used by the site-wide search bar.  CSRF is disabled
because the form is submitted via GET.
"""

from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Length


class GlobalSearchForm(FlaskForm):
    """Site-wide search form rendered in the navigation bar.

    Requires at least two characters to prevent overly broad queries.
    CSRF is disabled for GET-based submission.
    """

    class Meta:
        csrf = False

    q = StringField(
        "Search",
        validators=[DataRequired(), Length(min=2)],
    )
