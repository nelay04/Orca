from django import forms
import re
from datetime import datetime


class SigninForm(forms.Form):
    email = forms.EmailField(
        required=True,
        error_messages={
            "required": "Email is required.",
            "invalid": "Please enter a valid email address.",
        },
    )


class SignupForm(forms.Form):
    full_name = forms.CharField(
        required=True,
        min_length=2,
        error_messages={
            "required": "Full name is required.",
            "min_length": "Full name must be at least 2 characters long.",
        },
    )
    gender = forms.ChoiceField(
        required=True,
        choices=[
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
            ("prefer_not_to_say", "Prefer not to say"),
        ],
        error_messages={
            "required": "Gender is required.",
            "invalid_choice": "Gender must be one of 'Male', 'Female', 'Other' or 'prefer not to say'.",
        },
    )
    dob = forms.DateField(
        required=True,
        error_messages={
            "required": "Date of birth is required.",
            "invalid": "Invalid date of birth format. Use 'YYYY-MM-DD'.",
        },
    )

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name")
        if not re.match(r"^[A-Za-z ]+$", full_name):
            raise forms.ValidationError(
                "Name must only contain letters (A-Z or a-z) and spaces."
            )
        if not full_name.replace(" ", "").isalpha():
            raise forms.ValidationError("Full name should only contain alphabets.")
        return full_name

    def clean_dob(self):
        dob = self.cleaned_data.get("dob")
        # dob is already a datetime.date object because of DateField
        if dob and dob > datetime.now().date():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob
