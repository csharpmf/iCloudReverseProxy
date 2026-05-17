from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from playwright.async_api import TimeoutError

@dataclass
class Conf:
    email: str
    password: str
    code: str


async def start_login(
    creds: Conf,
    playwright
) -> tuple:
    # if not isinstance(creds.email, str):
    #     raise TypeError("email must be a string")
    # if not isinstance(creds.password, str):
    #     raise TypeError("password must be a string")
    # if not isinstance(creds.code, str):
    #     raise TypeError("code must be a string")

    browser = await playwright.chromium.launch(
        headless=False
    )
    context = await browser.new_context()
    page = await context.new_page()

    await page.goto(
        "https://www.icloud.com/"
    )
    await page.wait_for_load_state(
        "domcontentloaded"
    )

    await page.get_by_role(
        "button",
        name="Sign In"
    ).click()

    iframe_element = await page.wait_for_selector(
        'iframe',
        timeout=10000
    )

    iframe = await iframe_element.content_frame()
    if iframe is None:
        raise RuntimeError(
            "iframe content frame not available"
        )

    await iframe.wait_for_selector(
        'input[id="account_name_text_field"]'
    )

    await iframe.fill(
        'input[id="account_name_text_field"]',
        creds.email
    )

    await iframe.wait_for_timeout(
        500
    )

    await iframe.press(
        'input[id="account_name_text_field"]',
        "Enter"
    )

    try:
        await iframe.wait_for_selector(
            'button[id="continue-password"]',
            timeout=1500
        )
        await iframe.click(
            'button[id="continue-password"]'
        )
    except:
        pass

    await iframe.wait_for_selector(
        'input[id="password_text_field"]',
        timeout=10000
    )

    await iframe.fill(
        'input[id="password_text_field"]',
        creds.password
    )

    await iframe.press(
        'input[id="password_text_field"]',
        "Enter"
    )

    try:
        await iframe.wait_for_selector(
            'p#errMsg',
            timeout=1000
        )
        await context.close()
        await browser.close()
        raise RuntimeError("Invalid password")
    except TimeoutError:
        pass

    try:
        await iframe.wait_for_selector(
            'h1',
            timeout=5000
        )

        h1_text = await iframe.locator("h1").inner_text()
        if "Two-Factor Authentication" in h1_text:
            return browser, context, page, "2fa"

    except TimeoutError:
        pass

    username = creds.email.split("@")[0]
    cookie_file = Path(
        f"users/user_{username}.json"
    )
    await context.storage_state(
        path=str(
            cookie_file
        )
    )
    await context.close()
    await browser.close()
    return None, None, None, "authenticated"


async def f_2fa(
    creds: Conf,
    browser,
    context,
    page
) -> None:
    iframe_el = await page.main_frame.query_selector(
        'iframe'
    )
    iframe = await iframe_el.content_frame()

    for _ in range(10):  # max ~5s
        inputs = await iframe.locator(
            'input.form-security-code-input'
        ).all()
        if len(inputs) == 6:
            break
        await page.wait_for_timeout(
            500
        )
    else:
        ...

    if len(creds.code) != 6 or not creds.code.isdigit():
        raise RuntimeError(
            "2fa has to be 6 digits"
        )

    for i, digit in enumerate(
        creds.code
    ):
        await inputs[i].fill(
            digit
        )

    for _ in range(20):  # up to ~10s
        await page.wait_for_timeout(
            500
        )
        iframe_el = await page.main_frame.query_selector(
            'iframe'
        )
        if iframe_el:
            iframe_or_page = await iframe_el.content_frame()
        else:
            iframe_or_page = page

        h1_el = await iframe_or_page.query_selector(
            'h1.tk-intro'
        )
        if h1_el:
            h1_text = await h1_el.inner_text()
            if "Trust this browser?" in h1_text:
                break
    else:
        ...

    await page.wait_for_timeout(
        1000
    )

    try:
        await iframe_or_page.wait_for_selector(
            'span.form-message',
            timeout=2000
        )
        error_text = await iframe_or_page.locator(
            'span.form-message'
        ).inner_text()

        if "Incorrect verification code" in error_text:
            raise RuntimeError(
                "Incorrect verification code"
            )
    except TimeoutError:
        pass

    trust_button = await iframe_or_page.query_selector(
        'button.button.button-rounded-rectangle[type="submit"]'
    )
    if not trust_button:
        raise RuntimeError(
            "couldnt find trust button [??]"
        )

    await trust_button.click()
    print(
        "trusted ts"
    )

    await page.wait_for_timeout(
        3000
    )

    username = creds.email.split("@")[0]
    cookie_file = Path(
        f"users/user_{username}.json"
    )
    await context.storage_state(
        path=str(
            cookie_file
        )
    )
    await context.close()
    await browser.close()
