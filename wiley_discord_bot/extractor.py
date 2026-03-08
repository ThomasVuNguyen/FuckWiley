import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

async def run_extraction(job, update_status_callback):
    """
    Runs the Playwright headless extraction loop.
    job: An ExtractionJob object from bot.py containing url, email, password, and pages.
    update_status_callback: An async function accepting a string message to send back to the user on Discord.
    
    Returns the path to the combined markdown file upon success.
    """
    output_dir = f"extractions/{job.user.id}_{job.pages}_pages"
    os.makedirs(output_dir, exist_ok=True)
    
    markdown_output_file = os.path.join(output_dir, "extracted_book.md")
    
    # Initialize the markdown file
    with open(markdown_output_file, 'w') as f:
        f.write(f"# Extracted Book\n\nSource: {job.book_url}\n\n---\n\n")

    await update_status_callback("Launching safe headless browser...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Setting a generic user agent to avoid bot detection
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()

        try:
            # 1. Navigate to the Slingshot SSO Page
            await update_status_callback("Logging into Indiana Wesleyan SSO...")
            await page.goto("https://indwes.slingshotedu.com/login")
            
            # Wait for email and password fields
            await page.wait_for_selector('input#email', timeout=15000)
            await page.fill('input#email', job.email)
            
            await page.wait_for_selector('input#password', timeout=5000)
            await page.fill('input#password', job.password)
            
            # Click sign in
            await page.click('button:has-text("Log")')
            
            # Wait for authentication to complete
            await update_status_callback("Waiting for SSO authentication to complete...")
            await asyncio.sleep(8)
            
            # 2. Navigate to the actual book URL provided
            await update_status_callback(f"Opening book at provided URL...")
            await page.goto(job.book_url)
            
            # Wait for the reader to load the actual content
            # The previous script waited for #pbk-page structure
            await page.wait_for_selector('#pbk-page', timeout=30000)
            await asyncio.sleep(5) # Let animations and images settle

            await update_status_callback(f"Book opened! Starting extraction of {job.pages} pages...")

            for i in range(1, job.pages + 1):
                page_status = f"Extracting page {i}/{job.pages}..."
                print(page_status)
                
                # Hide UI elements to get a clean screenshot using JS evaluation
                await page.evaluate('''() => {
                    const uiElements = document.querySelectorAll('.app-navbar, .reader-toolbar, vn-brand-bar, .side-panel');
                    uiElements.forEach(el => {
                        if (el) el.style.visibility = 'hidden';
                    });
                }''')
                
                # Take screenshot
                screenshot_path = os.path.join(output_dir, f"page_{i}.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                
                # Restore UI elements (needed for clicking Next)
                await page.evaluate('''() => {
                    const uiElements = document.querySelectorAll('.app-navbar, .reader-toolbar, vn-brand-bar, .side-panel');
                    uiElements.forEach(el => {
                        if (el) el.style.visibility = 'visible';
                    });
                }''')
                
                # Process with Codex API
                # Pass the image to GPT-5.4 proxy CLI
                cmd = [
                    "npx", "codex", "exec", 
                    "-c", "models.gpt-5.4.supported_by_chatgpt=true", 
                    "-c", "model=gpt-5.4", 
                    "-i", screenshot_path, 
                    "--", "Extract the text from this textbook page perfectly into Markdown. Do not include any conversational filler, just the exact textbook text. If there are headers, format them as markdown headers. If there are images, just write [Image: <brief description>]."
                ]
                
                process = subprocess.run(cmd, capture_output=True, text=True, cwd='/home/thomas/development/internal/FuckWiley')
                
                if process.returncode == 0:
                    extracted_text = process.stdout.strip()
                    with open(markdown_output_file, 'a') as f:
                        f.write(f"\n\n<!-- PAGE {i} -->\n\n")
                        f.write(extracted_text)
                else:
                    error_msg = f"Failed to extract text for page {i}.\nError: {process.stderr}"
                    print(error_msg)
                    with open(markdown_output_file, 'a') as f:
                        f.write(f"\n\n<!-- ERROR ON PAGE {i} -->\n\n")
                        f.write("Could not extract text due to CLI error.")
                
                # Go to next page if not the last page
                if i < job.pages:
                    try:
                        # Click the next page button
                        await page.click('button[aria-label="Next page"]')
                        await asyncio.sleep(3) # Wait for page turn animation and load
                        await page.wait_for_selector('#pbk-page', state='visible', timeout=10000)
                    except Exception as e:
                        print(f"Failed to turn to next page after page {i}: {e}")
                        await update_status_callback(f"⚠️ Warning: Encountered an issue turning the page after page {i}. Extraction might end early.")
                        break

            await update_status_callback("Extraction loop complete. Finalizing document...")
            
        except Exception as e:
            print(f"Error during Playwright execution: {e}")
            raise e
        finally:
            await browser.close()
            
    return markdown_output_file
