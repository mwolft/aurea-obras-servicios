"""Small, client-compatible building blocks for AUREA emails."""

from dataclasses import dataclass
from html import escape


BRAND_NAME = "AUREA"
BRAND_SUBTITLE = "OBRAS Y SERVICIOS"
NAVY = "#102A43"
ORANGE = "#FF6200"
PAGE_BACKGROUND = "#F6F3EE"
SURFACE = "#FFFFFF"
TEXT = "#20252B"
MUTED_TEXT = "#52606D"
EMAIL_MAX_WIDTH = "600px"


@dataclass(frozen=True)
class EmailContent:
    """The HTML and plain-text alternatives for a single email."""

    html: str
    text: str


def escape_email_text(value: object) -> str:
    """Escape dynamic values before placing them in email HTML."""

    return escape(str(value), quote=True)


def escape_multiline_text(value: object) -> str:
    """Escape user content and retain its line breaks in HTML."""

    normalized_value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return escape_email_text(normalized_value).replace("\n", "<br>")


def information_row(label: str, value: object) -> str:
    """Render a consistently styled label/value row for trusted email content."""

    return f"""
      <tr>
        <td style="padding: 8px 0; color: {MUTED_TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 20px; vertical-align: top; width: 140px;">
          {escape_email_text(label)}
        </td>
        <td style="padding: 8px 0; color: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 20px; vertical-align: top;">
          {escape_email_text(value)}
        </td>
      </tr>
    """


def information_block(rows_html: str) -> str:
    """Wrap pre-rendered information rows in a compatible table."""

    return f"""
      <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse: collapse; width: 100%;">
        {rows_html}
      </table>
    """


def message_block(title: str, message: object) -> str:
    """Render safely escaped multiline content in the common card style."""

    return f"""
      <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="background: {PAGE_BACKGROUND}; border-collapse: collapse; border-left: 4px solid {ORANGE}; margin-top: 24px; width: 100%;">
        <tr>
          <td style="padding: 18px 20px;">
            <p style="color: {NAVY}; font-family: Arial, Helvetica, sans-serif; font-size: 14px; font-weight: 700; letter-spacing: 0.04em; line-height: 20px; margin: 0 0 10px; text-transform: uppercase;">{escape_email_text(title)}</p>
            <p style="color: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 15px; line-height: 24px; margin: 0;">{escape_multiline_text(message)}</p>
          </td>
        </tr>
      </table>
    """


def action_button(label: str, href: str) -> str:
    """Render a future reusable CTA without relying on external CSS."""

    return f"""
      <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse: collapse; margin-top: 24px;">
        <tr>
          <td bgcolor="{ORANGE}" style="border-radius: 4px;">
            <a href="{escape_email_text(href)}" style="background: {ORANGE}; border: 1px solid {ORANGE}; border-radius: 4px; color: #FFFFFF; display: inline-block; font-family: Arial, Helvetica, sans-serif; font-size: 14px; font-weight: 700; line-height: 20px; padding: 12px 18px; text-decoration: none;">{escape_email_text(label)}</a>
          </td>
        </tr>
      </table>
    """


def render_email(*, title: str, preheader: str, body_html: str, footer_text: str) -> str:
    """Render AUREA's shared email shell around trusted body HTML helpers."""

    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape_email_text(title)}</title>
  </head>
  <body style="background: {PAGE_BACKGROUND}; margin: 0; padding: 0;">
    <div style="display: none; font-size: 1px; line-height: 1px; max-height: 0; max-width: 0; opacity: 0; overflow: hidden;">{escape_email_text(preheader)}</div>
    <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="background: {PAGE_BACKGROUND}; border-collapse: collapse; width: 100%;">
      <tr>
        <td align="center" style="padding: 32px 16px;">
          <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse: collapse; margin: 0 auto; max-width: {EMAIL_MAX_WIDTH}; width: 100%;">
            <tr>
              <td style="background: {NAVY}; padding: 24px 28px;">
                <p style="color: #FFFFFF; font-family: Arial, Helvetica, sans-serif; font-size: 24px; font-weight: 700; letter-spacing: 0.08em; line-height: 28px; margin: 0;">{BRAND_NAME}</p>
                <p style="color: #FFFFFF; font-family: Arial, Helvetica, sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 0.14em; line-height: 16px; margin: 4px 0 0;">{BRAND_SUBTITLE}</p>
              </td>
            </tr>
            <tr>
              <td style="background: {SURFACE}; padding: 32px 28px;">
                <h1 style="color: {NAVY}; font-family: Arial, Helvetica, sans-serif; font-size: 24px; font-weight: 700; line-height: 32px; margin: 0 0 24px;">{escape_email_text(title)}</h1>
                {body_html}
              </td>
            </tr>
            <tr>
              <td style="border-top: 3px solid {ORANGE}; padding: 18px 28px 0;">
                <p style="color: {MUTED_TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 12px; line-height: 18px; margin: 0;">{escape_email_text(footer_text)}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
