from google.adk.agents.llm_agent import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.load_artifacts_tool import load_artifacts_tool
from google.genai import types

# Add webdriver manager if available
try:
    from webdriver_manager.chrome import ChromeDriverManager
    print("WebDriver Manager available for automatic driver management")
except ImportError:
    print("WebDriver Manager not available. Will use standard initialization.")

import time
import re
import urllib.parse
import random
from datetime import datetime
from PIL import Image
import json
import os
from typing import List, Dict, Any, Optional

import selenium
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException
)

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Constants
MAX_RETRIES = 3
PAGE_LOAD_TIMEOUT = 20  # Increased timeout
SEARCH_RESULTS_TO_VISIT = 100
MAX_TEXT_LENGTH = 50000  # Limit text to prevent token overflow
WAIT_BETWEEN_ACTIONS = 2  # Increased wait time between actions for more human-like behavior
SCROLL_INTERVAL = 500    # Pixels to scroll each time
SCROLL_PAUSE_TIME = 1    # Time to pause between scrolls

# Global variables
driver = None
tool_context_instance = None


# Browser setup - with better initialization
def setup_chrome_options():
    """Set up Chrome options with appropriate settings"""
    options = Options()
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--verbose")
    # Comment out headless mode for debugging
    # options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    return options

def initialize_driver():
    """Initialize the browser driver if not already initialized."""
    global driver
    if driver is None:
        try:
            print("🚀 Initializing Chrome browser...")
            options = setup_chrome_options()
            
            # Use ChromeDriverManager for automatic webdriver management
            # If ChromeDriverManager is not available, fall back to standard initialization
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                driver = selenium.webdriver.Chrome(service=service, options=options)
            except ImportError:
                print("Using standard Chrome initialization...")
                driver = selenium.webdriver.Chrome(options=options)
                
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            print(f"✅ Browser initialized successfully. Version: {driver.capabilities['browserVersion']}")
            return "Browser initialized successfully"
        except Exception as e:
            print(f"❌ Browser initialization failed: {str(e)}")
            # Try alternative initialization methods
            try:
                print("Attempting alternative browser initialization...")
                options = setup_chrome_options()
                driver = selenium.webdriver.Chrome(options=options)
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                return "Browser initialized successfully with alternative method"
            except Exception as e2:
                return f"Failed to initialize browser: {str(e2)}. Make sure Chrome is installed."
    return "Browser already initialized"

def go_to_url(url: str) -> str:
    """Navigates the browser to the given URL with retry logic."""
    initialize_driver()
    print(f"🌐 Navigating to URL: {url}")
    
    # Add http prefix if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    for attempt in range(MAX_RETRIES):
        try:
            driver.get(url.strip())
            # Allow some time for JavaScript content to load
            time.sleep(WAIT_BETWEEN_ACTIONS)
            
            # Simulate human-like scrolling behavior right after loading
            perform_human_scrolling()
            
            return f"Successfully navigated to: {url}"
        except TimeoutException:
            if attempt < MAX_RETRIES - 1:
                print(f"Timeout while loading {url}, retry {attempt + 1}")
                continue
            else:
                return f"Timeout error loading {url} after {MAX_RETRIES} attempts"
        except WebDriverException as e:
            return f"Error navigating to {url}: {str(e)}"

def perform_human_scrolling():
    """Simulates human-like scrolling behavior to load page content dynamically"""
    try:
        # Get initial page height
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        # Scroll a few times with random intervals to mimic human behavior
        scroll_attempts = random.randint(3, 6)
        for i in range(scroll_attempts):
            # Scroll down with variable distance
            scroll_amount = random.randint(300, 800)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            
            # Add random pause between scrolls (0.5 to 2 seconds)
            time.sleep(random.uniform(0.5, 2.0))
            
            # Sometimes scroll back up a little bit
            if random.random() > 0.7:  # 30% chance
                driver.execute_script(f"window.scrollBy(0, -{random.randint(100, 300)});")
                time.sleep(random.uniform(0.3, 1.0))
                
        # Finally, scroll to bottom to make sure we've loaded all content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(WAIT_BETWEEN_ACTIONS)
        
        # And back to a reasonable viewing position
        driver.execute_script("window.scrollTo(0, Math.max(document.body.scrollHeight / 3, 600));")
        
        print("✅ Performed human-like scrolling")
    except Exception as e:
        print(f"⚠️ Error during scrolling: {str(e)}")

def take_screenshot() -> dict:
    """Takes a screenshot and saves it with a timestamp."""
    initialize_driver()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    print(f"📸 Taking screenshot: {filename}")
    
    try:
        driver.save_screenshot(filename)
        print(f"Screenshot saved to {filename}")
        
        # We won't use tool_context to save artifacts, just return the file info
        return {"status": "success", "filename": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_page_title() -> str:
    """Returns the title of the current page."""
    initialize_driver()
    try:
        return driver.title
    except Exception as e:
        return f"Error getting page title: {str(e)}"

def get_page_source() -> str:
    """Returns the current page source (truncated to prevent token overflow)."""
    initialize_driver()
    print("📄 Getting page source...")
    try:
        source = driver.page_source
        if len(source) > MAX_TEXT_LENGTH:
            return source[:MAX_TEXT_LENGTH] + "\n... [truncated]"
        return source
    except Exception as e:
        return f"Error getting page source: {str(e)}"

def find_element_with_text(text: str) -> str:
    """Finds an element on the page with the given text."""
    initialize_driver()
    print(f"🔍 Finding element with text: '{text}'")
    
    try:
        # Try different XPath patterns for finding text
        xpath_patterns = [
            f"//*[contains(text(), '{text}')]",
            f"//*[text()='{text}']",
            f"//a[contains(., '{text}')]",
            f"//button[contains(., '{text}')]"
        ]
        
        for xpath in xpath_patterns:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                return f"Found {len(elements)} elements containing '{text}'"
        
        return f"No elements found containing '{text}'"
    except Exception as e:
        return f"Error finding element: {str(e)}"

def click_element_with_text(text: str) -> str:
    """Clicks on an element containing the specified text."""
    initialize_driver()
    print(f"🖱️ Clicking element with text: '{text}'")
    
    try:
        # Try multiple XPath patterns to find the element
        xpath_patterns = [
            f"//*[contains(text(), '{text}')]",
            f"//*[text()='{text}']",
            f"//a[contains(., '{text}')]",
            f"//button[contains(., '{text}')]",
            f"//*[contains(@title, '{text}')]",
            f"//*[contains(@aria-label, '{text}')]"
        ]
        
        for xpath in xpath_patterns:
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                for element in elements:
                    try:
                        # Try to scroll the element into view
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                        time.sleep(WAIT_BETWEEN_ACTIONS)
                        element.click()
                        time.sleep(WAIT_BETWEEN_ACTIONS)
                        return f"Successfully clicked element with text: '{text}'"
                    except (ElementNotInteractableException, ElementClickInterceptedException):
                        continue
                    except StaleElementReferenceException:
                        break
        
        # If no element was successfully clicked, try JavaScript click
        try:
            driver.execute_script(f"document.evaluate(\"//*[contains(text(), '{text}')]\", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click();")
            return f"Clicked element with text '{text}' using JavaScript"
        except Exception:
            pass
            
        return f"Could not click any element with text: '{text}'"
    except Exception as e:
        return f"Error clicking element: {str(e)}"

def click_link_by_url_pattern(pattern: str) -> str:
    """Clicks a link that contains the given URL pattern."""
    initialize_driver()
    print(f"🔗 Looking for link with URL pattern: '{pattern}'")
    
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and pattern.lower() in href.lower():
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", link)
                time.sleep(WAIT_BETWEEN_ACTIONS)
                link.click()
                time.sleep(WAIT_BETWEEN_ACTIONS)
                return f"Clicked link with URL containing '{pattern}'"
                
        return f"No link found with URL pattern '{pattern}'"
    except Exception as e:
        return f"Error clicking link: {str(e)}"

def enter_text_into_element(selector: str, text_to_enter: str, selector_type: str = "id") -> str:
    """Enters text into an element identified by the given selector.
    
    Args:
        selector: The element selector (id, name, css, xpath)
        text_to_enter: The text to enter
        selector_type: Type of selector (id, name, css, xpath)
    """
    initialize_driver()
    print(f"📝 Entering text '{text_to_enter}' using {selector_type} selector: {selector}")
    
    try:
        if selector_type.lower() == "id":
            element = driver.find_element(By.ID, selector)
        elif selector_type.lower() == "name":
            element = driver.find_element(By.NAME, selector)
        elif selector_type.lower() == "css":
            element = driver.find_element(By.CSS_SELECTOR, selector)
        elif selector_type.lower() == "xpath":
            element = driver.find_element(By.XPATH, selector)
        else:
            return f"Invalid selector type: {selector_type}"
        
        # Clear existing text and enter new text
        element.clear()
        # Type the text more like a human - with variable speed
        for char in text_to_enter:
            element.send_keys(char)
            # Small random delay between keystrokes
            time.sleep(random.uniform(0.05, 0.15))
            
        time.sleep(WAIT_BETWEEN_ACTIONS)
        return f"Entered text into {selector_type} selector: {selector}"
    except NoSuchElementException:
        return f"Element with {selector_type} '{selector}' not found"
    except Exception as e:
        return f"Error entering text: {str(e)}"

def press_enter() -> str:
    """Presses the Enter key on the active element."""
    initialize_driver()
    try:
        active_element = driver.switch_to.active_element
        active_element.send_keys(Keys.RETURN)
        time.sleep(WAIT_BETWEEN_ACTIONS)
        return "Pressed Enter key"
    except Exception as e:
        return f"Error pressing Enter: {str(e)}"

def scroll_down(pixels: int = 500) -> str:
    """Scrolls down the page by the specified number of pixels."""
    initialize_driver()
    print(f"⬇️ Scrolling down {pixels} pixels")
    try:
        # Make scrolling feel more natural with smooth motion
        driver.execute_script(f"""
        var pixelsToScroll = {pixels};
        var duration = 700;  // milliseconds
        var start = performance.now();
        var scrollStep = function(timestamp) {{
            var elapsed = timestamp - start;
            var progress = Math.min(elapsed / duration, 1);
            // Use ease-out function for more natural feel
            progress = 1 - Math.pow(1 - progress, 2);
            window.scrollBy(0, pixelsToScroll * progress - window.lastProgress || 0);
            window.lastProgress = pixelsToScroll * progress;
            if (elapsed < duration) {{ 
                window.requestAnimationFrame(scrollStep);
            }}
        }};
        window.lastProgress = 0;
        window.requestAnimationFrame(scrollStep);
        """)
        time.sleep(random.uniform(1.0, 2.0))  # Variable wait time
        return f"Scrolled down {pixels} pixels"
    except Exception as e:
        return f"Error scrolling: {str(e)}"

def scroll_to_bottom() -> str:
    """Scrolls to the bottom of the page gradually."""
    initialize_driver()
    print("⬇️ Scrolling to bottom of page")
    try:
        # Get initial page height
        total_height = driver.execute_script("return document.body.scrollHeight")
        current_position = driver.execute_script("return window.pageYOffset")
        viewport_height = driver.execute_script("return window.innerHeight")
        
        # Scroll in steps with variable speed
        while current_position + viewport_height < total_height:
            # Calculate a random scroll distance (between 300-800 pixels)
            scroll_step = random.randint(300, 800)
            driver.execute_script(f"window.scrollBy(0, {scroll_step});")
            
            # Random pause between scrolls
            time.sleep(random.uniform(0.3, 1.2))
            
            # Update position
            current_position = driver.execute_script("return window.pageYOffset")
            
            # Check if content height changed (dynamic loading)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height > total_height:
                total_height = new_height
        
        # Final scroll to ensure we're at the bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(WAIT_BETWEEN_ACTIONS)
        return "Scrolled to bottom of page"
    except Exception as e:
        return f"Error scrolling to bottom: {str(e)}"

def wait_for_element(selector: str, selector_type: str = "css", timeout: int = 10) -> str:
    """Waits for an element to be present on the page."""
    initialize_driver()
    print(f"⏳ Waiting for element with {selector_type} selector: {selector}")
    
    try:
        if selector_type.lower() == "id":
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.ID, selector))
            )
        elif selector_type.lower() == "css":
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        elif selector_type.lower() == "xpath":
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, selector))
            )
        else:
            return f"Invalid selector type: {selector_type}"
            
        return f"Element with {selector_type} '{selector}' found"
    except TimeoutException:
        return f"Timed out waiting for element with {selector_type}: {selector}"
    except Exception as e:
        return f"Error waiting for element: {str(e)}"

def extract_google_search_results() -> str:
    """Extracts search results from Google search page with enhanced robustness."""
    initialize_driver()
    print("🔍 Extracting Google search results")
    
    try:
        # Wait longer for results to load (increase from 10 to 15 seconds)
        time.sleep(3)  # Add initial pause to ensure page is loaded
        
        # Try multiple selector patterns to adapt to Google's changing structure
        result_selectors = [
            "div.g", 
            "div.yuRUbf", 
            "div[data-sokoban-container]",
            "div.tF2Cxc",
            "div.Gx5Zad",
            "div.egMi0"
        ]
        
        results = []
        
        # Try each selector pattern until we find results
        for selector in result_selectors:
            try:
                # Wait for results with this specific selector
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                # Find all search result containers with this selector
                result_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if result_elements and len(result_elements) > 0:
                    print(f"Found {len(result_elements)} results with selector: {selector}")
                    
                    for idx, result in enumerate(result_elements[:SEARCH_RESULTS_TO_VISIT]):
                        try:
                            # Extract title - try multiple approaches
                            title = None
                            for title_selector in ["h3", "h3.LC20lb", ".DKV0Md"]:
                                try:
                                    title_element = result.find_element(By.CSS_SELECTOR, title_selector)
                                    title = title_element.text
                                    if title:
                                        break
                                except Exception:
                                    continue
                            
                            # Extract URL - try multiple approaches
                            url = None
                            for link_selector in ["a", "a[href]", ".yuRUbf a"]:
                                try:
                                    link_element = result.find_element(By.CSS_SELECTOR, link_selector)
                                    url = link_element.get_attribute("href")
                                    if url:
                                        break
                                except Exception:
                                    continue
                            
                            # If we couldn't find title or URL directly in this element, try parent/child approach
                            if not title or not url:
                                # Try finding parent container and then looking for elements
                                parent = driver.execute_script("return arguments[0].parentNode;", result)
                                try:
                                    title_element = parent.find_element(By.CSS_SELECTOR, "h3")
                                    title = title_element.text
                                except Exception:
                                    pass
                                    
                                try:
                                    link_element = parent.find_element(By.CSS_SELECTOR, "a")
                                    url = link_element.get_attribute("href")
                                except Exception:
                                    pass
                            
                            if title and url:
                                # Only add if we haven't already found this URL
                                if not any(r["url"] == url for r in results):
                                    results.append({
                                        "position": len(results) + 1,
                                        "title": title,
                                        "url": url
                                    })
                        except Exception as e:
                            print(f"Error extracting result {idx}: {str(e)}")
                            continue
                    
                    # If we found at least 3 results, we can stop trying other selectors
                    if len(results) >= 3:
                        break
            except TimeoutException:
                print(f"Selector {selector} not found, trying next one")
                continue
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")
                continue
        
        # If we still don't have results, try a direct XPath approach
        if not results:
            print("Trying XPath approach...")
            try:
                # This XPath looks for any link that has an h3 element inside its tree
                links = driver.find_elements(By.XPATH, "//a[.//h3]")
                for idx, link in enumerate(links[:SEARCH_RESULTS_TO_VISIT]):
                    try:
                        url = link.get_attribute("href")
                        title_element = link.find_element(By.XPATH, ".//h3")
                        title = title_element.text
                        
                        if title and url:
                            results.append({
                                "position": idx + 1,
                                "title": title,
                                "url": url
                            })
                    except Exception:
                        continue
            except Exception as e:
                print(f"XPath approach failed: {str(e)}")
        
        # Last resort - try to get ALL links that seem like results
        if not results:
            print("Using last resort method for extracting results...")
            try:
                # Take a screenshot to help with debugging
                driver.save_screenshot("search_results_debug.png")
                
                # Get all links on the page
                all_links = driver.find_elements(By.TAG_NAME, "a")
                search_links = []
                
                # Filter for links that look like search results
                for link in all_links:
                    href = link.get_attribute("href")
                    
                    # Skip non-links and Google internal links
                    if not href or not href.startswith("http") or "google" in href:
                        continue
                        
                    # Get text either from the link itself or a nearby h3
                    link_text = link.text
                    
                    try:
                        # Try to find a nearby h3
                        parent = driver.execute_script("return arguments[0].parentNode;", link)
                        h3 = parent.find_element(By.TAG_NAME, "h3")
                        link_text = h3.text
                    except Exception:
                        pass
                    
                    if link_text and len(link_text) > 10:  # Likely a result title
                        search_links.append((link_text, href))
                
                # Add unique links to results
                for idx, (title, url) in enumerate(search_links[:SEARCH_RESULTS_TO_VISIT]):
                    if not any(r["url"] == url for r in results):
                        results.append({
                            "position": len(results) + 1,
                            "title": title,
                            "url": url
                        })
            except Exception as e:
                print(f"Last resort method failed: {str(e)}")
        
        if not results:
            return json.dumps([{"error": "Could not extract any search results using multiple methods"}])
        
        print(f"Successfully extracted {len(results)} search results")
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps([{"error": f"Error extracting search results: {str(e)}"}])

def extract_page_content() -> dict:
    """Extracts relevant content from the current page."""
    initialize_driver()
    print("📑 Extracting page content")
    
    try:
        # Basic page information
        page_info = {
            "title": driver.title,
            "url": driver.current_url,
            "extracted_at": datetime.now().isoformat(),
            "main_content": "",
            "meta_description": "",
            "headings": [],
            "paragraphs": [],
            "lists": [],
            "sections": []
        }
        
        # Get meta description
        try:
            meta_desc = driver.find_element(By.CSS_SELECTOR, "meta[name='description']")
            page_info["meta_description"] = meta_desc.get_attribute("content")
        except NoSuchElementException:
            pass
        
        # Extract headings
        for heading_level in range(1, 7):  # h1 through h6
            heading_elements = driver.find_elements(By.CSS_SELECTOR, f"h{heading_level}")
            for heading in heading_elements:
                if heading.text.strip():
                    page_info["headings"].append({
                        "level": heading_level,
                        "text": heading.text.strip()
                    })
        
        # Extract paragraph content with better structure
        paragraphs = driver.find_elements(By.CSS_SELECTOR, "p")
        for i, p in enumerate(paragraphs):
            text = p.text.strip()
            if text:
                page_info["paragraphs"].append({
                    "index": i+1,
                    "text": text
                })
        
        # Extract list items
        lists = driver.find_elements(By.CSS_SELECTOR, "ul, ol")
        for i, list_element in enumerate(lists):
            items = list_element.find_elements(By.CSS_SELECTOR, "li")
            list_items = []
            for item in items:
                if item.text.strip():
                    list_items.append(item.text.strip())
            
            if list_items:
                page_info["lists"].append({
                    "index": i+1,
                    "type": list_element.tag_name,
                    "items": list_items
                })
        
        # Extract article content if available
        try:
            article = driver.find_element(By.CSS_SELECTOR, "article")
            article_text = article.text
            if article_text:
                page_info["main_content"] = article_text[:MAX_TEXT_LENGTH]
        except NoSuchElementException:
            # Try alternative containers
            for selector in ["main", ".content", "#content", ".main-content", "#main"]:
                try:
                    main_content = driver.find_element(By.CSS_SELECTOR, selector)
                    content_text = main_content.text
                    if content_text and len(content_text) > 100:
                        page_info["main_content"] = content_text[:MAX_TEXT_LENGTH]
                        break
                except NoSuchElementException:
                    continue
            
            # If we still don't have main content, use paragraph content
            if not page_info["main_content"] and page_info["paragraphs"]:
                combined_text = "\n\n".join([p["text"] for p in page_info["paragraphs"]])
                page_info["main_content"] = combined_text[:MAX_TEXT_LENGTH]
        
        # Extract sections with headings - improved approach
        current_section = None
        for element in driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6, p, ul, ol"):
            tag_name = element.tag_name
            
            # If it's a heading, start a new section
            if tag_name.startswith('h'):
                if current_section:
                    # Add completed section if it has content
                    if current_section.get("content", "").strip():
                        page_info["sections"].append(current_section)
                
                # Start new section
                current_section = {
                    "heading": element.text.strip(),
                    "level": int(tag_name[1]),
                    "content": ""
                }
            # Otherwise add to current section content
            elif current_section:
                # Add content from paragraphs and lists
                current_section["content"] += element.text.strip() + "\n\n"
                
        # Add the last section if exists
        if current_section and current_section.get("content", "").strip():
            page_info["sections"].append(current_section)
        
        return page_info
    except Exception as e:
        return {"error": f"Error extracting page content: {str(e)}"}

def search_google(query: str) -> str:
    """Searches Google for the specified query."""
    initialize_driver()
    print(f"🔍 Searching Google for: {query}")
    
    # Format and encode the query
    formatted_query = query.strip().replace(" ", "+")
    search_url = f"https://www.google.com/search?hl=en&q={formatted_query}"
    
    # Navigate to Google search
    result = go_to_url(search_url)
    if "Error" in result or "Timeout" in result:
        return f"Failed to load Google search: {result}"
    
    time.sleep(WAIT_BETWEEN_ACTIONS * 2)  # Give more time for search results to load
    
    # Perform human-like scrolling to load all results
    perform_human_scrolling()
    
    return "Google search completed. Use extract_google_search_results() to get results."

def analyze_business_data(data_list: List[Dict[str, Any]]) -> str:
    """Analyzes collected business data and provides insights."""
    print("📊 Analyzing business data")
    
    analysis_prompt = f"""
    You are an expert business analyst specializing in providing insights on business niches.
    
    You have collected data from {len(data_list)} websites about a specific business niche. 
    Below is the collected data:
    
    {json.dumps(data_list, indent=2)}
    
    Please analyze this data and provide:
    
    1. Market Overview: Summarize the current state of this business niche
    2. Competitive Landscape: Who are the main players and how competitive is the space?
    3. Opportunity Assessment: What opportunities exist in this niche?
    4. Risk Analysis: What are the main risks and challenges?
    5. Profitability Potential: How profitable could this niche be?
    6. Entry Barriers: How difficult is it to enter this market?
    7. Recommendation: Should someone pursue this business idea? (Score 1-10)
    
    Focus on extracting factual information from the data provided, not making up details.
    If certain information is missing, note that it's not available rather than inventing it.
    
    Base your analysis strictly on the data collected from these websites.
    """
    
    return analysis_prompt

def extract_website_data(url: str) -> dict:
    """Visits a website and extracts relevant business data."""
    print(f"🌐 Extracting data from: {url}")
    
    # Navigate to the website
    result = go_to_url(url)
    if "Error" in result or "Timeout" in result:
        return {
            "url": url,
            "status": "failed",
            "error": result
        }
    
    # Basic data collection
    data = {
        "url": url,
        "title": get_page_title(),
        "status": "success",
        "content": {},
        "screenshots": []
    }
    
    try:
        # Take screenshot
        screenshot_result = take_screenshot(ToolContext())
        if screenshot_result.get("status") == "success":
            data["screenshots"].append(screenshot_result.get("filename"))
        
        # Extract page content
        content = extract_page_content()
        if "error" not in content:
            data["content"] = content
        else:
            data["content"] = {
                "error": content["error"],
                "title": data["title"],
                "raw_text": get_page_source()[:1000]  # Limited raw text as fallback
            }
        
        # Scroll to see more content
        for _ in range(3):
            scroll_down(700)
            time.sleep(1)
        
        # Take another screenshot after scrolling
        screenshot_result = take_screenshot(ToolContext())
        if screenshot_result.get("status") == "success":
            data["screenshots"].append(screenshot_result.get("filename"))
        
        return data
    except Exception as e:
        data["status"] = "partial"
        data["error"] = str(e)
        return data

def research_business_niche(niche: str, tool_context: ToolContext) -> str:
    """Orchestrates the entire business niche research process."""
    print(f"🔍 Researching business niche: {niche}")
    
    try:
        # Initialize browser if not already done
        initialize_driver()
        
        # Step 1: Search Google for the business niche
        search_google(f"{niche} business opportunity analysis profitable")
        
        # Step 2: Extract search results
        search_results_json = extract_google_search_results()
        search_results = json.loads(search_results_json)
        
        if not search_results:
            return "No search results found. Please try a different search query."
        
        # Step 3: Visit each website and collect data
        collected_data = []
        
        for idx, result in enumerate(search_results[:SEARCH_RESULTS_TO_VISIT]):
            print(f"Visiting result {idx+1}/{len(search_results[:SEARCH_RESULTS_TO_VISIT])}: {result['title']}")
            
            # Extract data from the website
            website_data = extract_website_data(result['url'])
            collected_data.append(website_data)
            
            # Take a short break between websites
            time.sleep(random.uniform(1.5, 3.0))
        
        # Step 4: Save the collected data
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        data_filename = f"business_niche_data_{timestamp}.json"
        
        with open(data_filename, 'w') as f:
            json.dump(collected_data, f, indent=2)
        
        # Step 5: Analyze the collected data
        analysis_prompt = analyze_business_data(collected_data)
        
        # Return summary of the research process
        return {
            "status": "completed",
            "niche": niche,
            "websites_analyzed": len(collected_data),
            "data_filename": data_filename,
            "analysis_prompt": analysis_prompt
        }
    except Exception as e:
        return f"Error researching business niche: {str(e)}"

def generate_business_ideas(interest: str, industry: str, budget: str, skill_level: str) -> str:
    """Generates business ideas based on user inputs."""
    print(f"💡 Generating business ideas for {interest} in {industry}")
    
    ideas_prompt = f"""
    As a business idea expert, generate 3 viable online business ideas based on:
    
    Interest: {interest}
    Industry: {industry}
    Budget: {budget}
    Skill Level: {skill_level}
    
    For each idea provide:
    - Idea Name
    - Description (2-3 sentences)
    - Market Demand (High/Medium/Low with brief explanation)
    - Monetization Potential (specific revenue streams)
    - Competitive Landscape (brief overview)
    - Risk Level (High/Medium/Low with explanation)
    - Suggestion Score (1-10)
    
    Focus on practical, actionable business ideas that match the user's parameters.
    Consider the skill level and budget constraints carefully.
    Provide specific rather than generic suggestions.
    """
    
    return ideas_prompt


from .prompt import SEARCH_RESULT_AGENT_PROMPT

# Create the agent with all enhanced tools
agent = Agent(
    model="gemini-2.0-flash-001",
    name="business_research_agent",
    description="Research business niches and provide detailed analysis",
    instruction=SEARCH_RESULT_AGENT_PROMPT,
    tools=[
        # Browser navigation
        initialize_driver,
        go_to_url,
        
        # Search functions
        search_google,
        extract_google_search_results,
        perform_human_scrolling,
        
        # Page interaction
        click_element_with_text,
        click_link_by_url_pattern,
        enter_text_into_element,
        press_enter,
        find_element_with_text,
        
        # Page navigation
        scroll_down,
        scroll_to_bottom,
        wait_for_element,
        
        # Content extraction
        get_page_title,
        get_page_source,
        extract_page_content,
        
        # Business analysis
        research_business_niche,
        generate_business_ideas,
        analyze_business_data,
        extract_website_data,
        
        # Utilities
        take_screenshot,
        load_artifacts_tool,
    ],
)
