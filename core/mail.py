from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives


_logos = [
    finders.find("images/logo.png"),
]


def _send_email(
    recipient, subject="", body_text="", body_html="", attachments=None, quiet=True
):
    """
    Sends email to recipient.
    """

    body_html = body_html or f"<p>{body_text}</p>"

    email = EmailMultiAlternatives(
        subject=subject,
        body=f"{body_text}\n",
        from_email=settings.EMAIL_FROM,
        to=[recipient],
        alternatives=[(body_html, "text/html")],
        attachments=attachments,
    )

    # always attach logos
    for img_path in _logos:
        if img_path:
            img_name = img_path.split("/")[-1]

            with open(img_path, "rb") as fp:
                img_file = MIMEImage(fp.read())

            img_file.add_header("Content-ID", f"<{img_name}>")

            email.attach(img_file)

    email.send(fail_silently=quiet)
    return email


def send_email(enqueue=False, *args, **kwargs):
    if settings.REDIS_ENABLED and enqueue:
        from django_rq import get_queue

        queue = get_queue(settings.RQ_SENDER_QUEUE)
        queue.enqueue(_send_email, *args, **kwargs)

    else:
        _send_email(*args, **kwargs)
