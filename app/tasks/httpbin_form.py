"""Example 2 - an interactive process (fill + submit a form) with OUTCOME CODES.

    make run TASK=httpbin_form INPUT="customer=Jane email=jane@example.com size=large"

This is the recommended pattern for production tasks: the agent must finish with exactly one
`outcome` from a fixed Literal list, plus the `evidence` text it saw. Your code then branches on
the outcome instead of parsing free text. See docs/PROMPTING_GUIDE.md.
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.tasks.base import BaseTask

Outcome = Literal[
    "SUBMITTED",        # the form was sent and the server echoed the data back
    "FORM_NOT_FOUND",   # the page did not show the expected form
    "SUBMIT_FAILED",    # clicked submit but no response / an error page
]


class FormResult(BaseModel):
    outcome: Outcome = Field(description="The single code that describes what happened.")
    evidence: str = Field(default="", max_length=300, description="Exact text you saw that proves it.")
    echoed_customer: str = Field(default="", description="custname value shown in the server response")
    echoed_size: str = Field(default="", description="size value shown in the server response")


class HttpbinForm(BaseTask):
    name = "httpbin_form"
    description = "Fill and submit the httpbin.org demo pizza form (interactive example)."
    required_inputs = ["customer"]
    optional_inputs = {"email": "test@example.com", "size": "medium"}
    start_url = "https://httpbin.org/forms/post"
    allowed_domains = ["httpbin.org"]
    Output = FormResult
    max_steps = 15
    system_rules = "Act carefully like a person. Never submit the form more than once."

    def prompt(self) -> str:
        i = self.inputs
        return f"""Submit the pizza order form on httpbin.org.

Data:
  Customer name: {i['customer']}
  E-mail: {i['email']}
  Size: {i['size']}
  Toppings: bacon and cheese

Steps:
1. You are on https://httpbin.org/forms/post. If the order form is not visible, finish with FORM_NOT_FOUND.
2. Fill in customer name, e-mail, choose the size and tick the two toppings.
3. Click "Submit order" exactly ONCE.
4. The server answers with a JSON page.
   - If it shows the "form" data you sent -> finish with SUBMITTED, and copy custname and size from it.
   - Otherwise -> finish with SUBMIT_FAILED.

Finish with done and the structured result. Put the exact text you saw in evidence.
"""
