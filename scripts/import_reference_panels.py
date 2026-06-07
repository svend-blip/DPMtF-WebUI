import sqlite3
import os
import re
from pathlib import Path

# Database path
DB_PATH = "databases/dpmtf.db"

def import_reference_panels():
    # Check if the source file exists
    source_file_path = "/home/svend/ai-pc-resource-webui/templates/index.html"
    if not os.path.exists(source_file_path):
        print(f"Error: Source file not found at {source_file_path}")
        return 0

    # Read the source HTML file
    with open(source_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Find all panel sections using regex to detect <section ...> tags
    # This pattern looks for section tags with panel-related classes
    panel_pattern = re.compile(r'<section[^>]*class=["\'][^"\']*panel[^"\']*["\'][^>]*>.*?</section>', re.DOTALL | re.IGNORECASE)
    panel_elements = panel_pattern.findall(html_content)

    # Count imported panels
    imported_count = 0

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Process each panel element
    for i, panel_element in enumerate(panel_elements):
        # Extract panel information using regex
        # Get the panel key from the id attribute
        id_match = re.search(r'id=["\']([^"\']*)["\']', panel_element, re.IGNORECASE)
        panel_key = id_match.group(1) if id_match else f'panel_{i}'

        # Get the html_id
        html_id = id_match.group(1) if id_match else ''

        # Get panel title from panel key (replace hyphens with spaces and title case)
        panel_title = panel_key.replace('-', ' ').title()

        # Get the raw opening tag for reference
        raw_opening_tag = panel_element.split('>', 1)[0] + '>' if '>' in panel_element else panel_element

        # Default sort order
        sort_order = i

        # Source file path
        source_file = source_file_path

        # Check if panel already exists by panel_key
        cursor.execute("SELECT id FROM frontend_panels WHERE panel_key = ?", (panel_key,))
        existing_panel = cursor.fetchone()

        if existing_panel:
            # Update existing panel
            cursor.execute("""
                UPDATE frontend_panels
                SET source_file = ?, panel_title = ?, html_id = ?, sort_order = ?, raw_opening_tag = ?, updated_at = CURRENT_TIMESTAMP
                WHERE panel_key = ?
            """, (source_file, panel_title, html_id, sort_order, raw_opening_tag, panel_key))
        else:
            # Insert new panel
            cursor.execute("""
                INSERT INTO frontend_panels (source_file, panel_key, panel_title, html_id, sort_order, raw_opening_tag)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (source_file, panel_key, panel_title, html_id, sort_order, raw_opening_tag))

            # Create a default classification for this panel
            panel_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO panel_classifications (panel_id, classification)
                VALUES (?, 'unknown')
            """, (panel_id,))

            imported_count += 1

    # Commit changes
    conn.commit()
    conn.close()

    print(f"Imported {imported_count} new panels from {source_file_path}")
    return imported_count

if __name__ == "__main__":
    import_reference_panels()