# url_validator.py
# Description: This script checks a list of URLs to see if they are valid and accessible.
# It separates the valid URLs from the invalid ones, which can then be used in
# another script.

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
# PASTE ALL THE URLS YOU WANT TO CHECK HERE
URLS_TO_CHECK = [
    # Traditional Indian Farming & Prior Entries
    "https://sdiopr.s3.ap-south-1.amazonaws.com/2023/June/16-Jun-23-2/2023_IJECC_101437/Revised-ms_IJECC_101437_v1.pdf",
    "https://icar.org.in/sites/default/files/2022-06/IITKA_Book_Traditional-Knowledge-in-Agriculture-English_0_0.pdf",
    "https://api.pageplace.de/preview/DT0400.9789389547627_A41783548/preview-9789389547627_A41783548.pdf",
    "https://egyankosh.ac.in/bitstream/123456789/59823/1/Indian%20Farmers%E2%80%98%20Traditions.pdf",
    "https://en.wikipedia.org/wiki/Barahnaja",
    "https://en.wikipedia.org/wiki/Jhum",
    "https://www.researchgate.net/publication/378256928_Exploring_Traditional_Agricultural_Techniques_Integrated_with_Modern_Farming_for_a_Sustainable_Future_A_Review",
    "https://www.researchgate.net/publication/393066472_Traditional_Organic_Farming_in_India_Merging_Ancient_Practices_with_Modern_Bio-Inputs_and_Green_Technologies/download",
    "https://wjbphs.com/sites/default/files/WJBPHS-2024-0850.pdf",
    "https://www.bhumipublishing.com/wp-content/uploads/2024/07/Farming-the-Future-Advanced-Techniques-in-Modern-Agriculture-Volume-I.pdf",
    "https://www.bhumipublishing.com/wp-content/uploads/2024/07/Farming-the-Future-Advanced-Techniques-in-Modern-Agriculture-Volume-II.pdf",
    "https://www.nabard.org/hindi/auth/writereaddata/tender/1507224157Paper-5-Agricultural-Tech-in-India-Dr.Joshi-%26-Varshney.pdf",
    "https://www.ijnrd.org/papers/IJNRD2208088.pdf",
    "https://en.wikipedia.org/wiki/Zero_Budget_Natural_Farming",
    "https://apnews.com/article/fbf86b092b42303f5ae9d8af35aac8d9",
    "https://timesofindia.indiatimes.com/city/nagpur/bhandara-farmers-adopt-natural-farming-for-sustainable-yields/articleshow/122768671.cms",
    "https://en.wikipedia.org/wiki/Contour_plowing",
    "https://www.frontiersin.org/journals/political-science/articles/10.3389/fpos.2022.969835/full",
    "https://apnews.com/article/fbf86b092b42303f5ae9d8af35aac8d9",  # duplicate for adoption context
    "https://timesofindia.indiatimes.com/city/nagpur/bhandara-farmers-adopt-natural-farming-for-sustainable-yields/articleshow/122768671.cms",
    #  New: Crop–Soil–Weather Recommender & General Guides
    "https://www.agritech.tnau.ac.in/pdf/AGRICULTURE.pdf",  # Comprehensive crop production guide (includes crop-soil-climate)
    "https://www.cropweatheroutlook.in/crida/amis/AICRPAM%20Bulletin%20%28District%20Level%20Wthr%20Calendars%29.pdf",  # District-level crop weather calendars in India
    "https://www.researchgate.net/publication/325863177_CROPS_RECOMMENDATION_BASED_ON_SOILS_AND_WEATHER_PREDICTION",  # AI-based crop-recommendation tool
    "https://buat.edu.in/wp-content/uploads/2023/10/001-Final-MS_Rainfes-Agriculture_AniketKalhapure.pdf",  # Rainfed Agriculture & Watershed Management
    "https://ignca.gov.in/Asi_data/75393.pdf",  # ‘Agriculture in India, Volume II: Crops’
    "https://nishat2013.files.wordpress.com/2013/11/agronomy-book.pdf",  # General Agronomy textbook overview

        "https://sdiopr.s3.ap-south-1.amazonaws.com/2023/June/16-Jun-23-2/2023_IJECC_101437/Revised-ms_IJECC_101437_v1.pdf",
    # ... (All previous links) ...
    "https://nishat2013.files.wordpress.com/2013/11/agronomy-book.pdf",
    
    #  New Added Resources – Crop-Climate-Soil Guidance
    "https://raubikaner.org/wp-content/themes/theme2/PDF/AGRON-111.pdf",  # Agronomy overview: soil, crop, water management
    "https://icar-crida.res.in/assets/img/Books/2003-04/ImpAgro.pdf",  # Improved Agronomic Practices for Dryland Crops (ICAR–CRIDA)
    "https://isa-india.in/wp-content/uploads/2018/02/Extended-Summaries-book-Vol.-3.pdf",  # Climate Smart Agronomy summaries
    "https://www.iari.res.in/files/Publication/important-publications/ClimateChange.pdf",  # Climate Change & Indian Agriculture—impact and adaptation
    "https://dst.gov.in/sites/default/files/Report_DST_CC_Agriculture.pdf",  # DST report on climate change & agriculture
    "https://ndl.ethernet.edu.et/bitstream/123456789/88789/1/Agronomic%20Handbook.pdf",  # Agronomic handbook: major crops, soil classification
    "https://k8449r.weebly.com/uploads/3/0/7/3/30731055/principles-of-agronomy-agricultural-meteorology-signed.pdf",  # Principles of Agronomy & Agricultural Meteorology
    "https://www.researchgate.net/publication/222849119_Indian_Agriculture_and_climate_sensitivity",  # Indian Agriculture & Climate Sensitivity (ResearchGate)

]

def check_url(url):
    """
    Checks a single URL by sending a HEAD request.
    Returns the URL and its status ('Valid' or 'Invalid' with a reason).
    """
    try:
        # Use a HEAD request for efficiency, timeout after 10 seconds
        response = requests.head(url, allow_redirects=True, timeout=10)
        
        # Consider any 2xx status code as success
        if response.status_code >= 200 and response.status_code < 300:
            return url, "Valid"
        else:
            return url, f"Invalid (Status Code: {response.status_code})"
            
    except requests.exceptions.Timeout:
        return url, "Invalid (Error: Timed out)"
    except requests.exceptions.RequestException as e:
        # Catches connection errors, invalid domains, etc.
        return url, f"Invalid (Error: {type(e).__name__})"
    except Exception as e:
        return url, f"Invalid (An unexpected error occurred: {e})"


def validate_urls_concurrently(urls):
    """
    Uses multiple threads to validate a list of URLs concurrently for speed.
    """
    valid_urls = []
    invalid_urls = []

    print(f"Starting validation for {len(urls)} URLs...")
    
    # Use ThreadPoolExecutor to check URLs in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Create a future for each URL check
        future_to_url = {executor.submit(check_url, url): url for url in urls}
        
        for i, future in enumerate(as_completed(future_to_url)):
            url = future_to_url[future]
            try:
                _, status = future.result()
                print(f"({i+1}/{len(urls)}) Checked: {url} -> {status}")
                if status == "Valid":
                    valid_urls.append(url)
                else:
                    invalid_urls.append((url, status))
            except Exception as exc:
                status = f"Invalid (Generated an exception: {exc})"
                print(f"({i+1}/{len(urls)}) Checked: {url} -> {status}")
                invalid_urls.append((url, status))

    return valid_urls, invalid_urls


if __name__ == "__main__":
    valid, invalid = validate_urls_concurrently(URLS_TO_CHECK)
    
    print("\n" + "="*40)
    print("           VALIDATION COMPLETE")
    print("="*40)

    # FIX: Replaced emoji with simple text to prevent UnicodeEncodeError on Windows
    print(f"\n[+] Valid URLs ({len(valid)}):")
    if valid:
        for url in valid:
            print(f"  - {url}")
    else:
        print("  None")
        
    # FIX: Replaced emoji with simple text
    print(f"\n[-] Invalid URLs ({len(invalid)}):")
    if invalid:
        for url, reason in invalid:
            print(f"  - {url}\n    Reason: {reason}")
    else:
        print("  None")
        
    print("\n" + "="*40)
    print("You can now copy the list of valid URLs into your embedding script.")
