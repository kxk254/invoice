import os, subprocess
import datetime
import shutil
import glob # Needed to find the latest file

# --- Configuration ---
# Replace with your actual paths relative to where Django runs or absolute paths
# IMPORTANT: Ensure the user running the Django process has permissions
# to read SOURCE_DB_PATH and write to LOCAL_BACKUP_DIR and NAS_BACKUP_DIR.
SOURCE_DB_PATH = '/invoice/db/db.sqlite3'
LOCAL_BACKUP_DIR = '/invoice/db/db_backups/'
NAS_BACKUP_DIR = '/invoice/nas_backups_mount'
# NAS_BACKUP_DIR = '/mnt/nas/develop/receipt/db_backups'

def _find_latest_local_backup_path():
    """Finds the path of the most recently modified file in the local backup directory."""
    if not os.path.exists(LOCAL_BACKUP_DIR):
        return None # Directory doesn't exist yet

    try:
        # List files, filter directories, get full paths
        list_of_files = glob.glob(os.path.join(LOCAL_BACKUP_DIR, '*'))
        latest_file = max(list_of_files, key=os.path.getmtime)
        return latest_file
    except ValueError:
        # No files found in the directory
        return None
    except Exception as e:
        # Catch other potential errors during file listing/sorting
        raise Exception(f"Error finding latest local backup: {e}")


def copy_local_db():
    """Copies the source DB to a local backup with a timestamp."""
    if not os.path.exists(SOURCE_DB_PATH):
        raise FileNotFoundError(f"Source database not found at {SOURCE_DB_PATH}")

    # Ensure local backup directory exists
    os.makedirs(LOCAL_BACKUP_DIR, exist_ok=True)

    try:
        # Create timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Get original database filename
        db_filename = os.path.basename(SOURCE_DB_PATH)
        # Construct new filename (e.g., mydatabase_20231027_103000.db)
        base, ext = os.path.splitext(db_filename)
        new_db_filename = f"{base}_{timestamp}{ext}"

        # Construct the full path for the local copy
        local_copy_path = os.path.join(LOCAL_BACKUP_DIR, new_db_filename)

        # Perform the copy
        shutil.copy2(SOURCE_DB_PATH, local_copy_path) # copy2 attempts to preserve metadata

        return local_copy_path # Return the path of the created backup

    except PermissionError:
        raise PermissionError(f"Permission denied. Cannot write to {LOCAL_BACKUP_DIR}.")
    except Exception as e:
        raise Exception(f"An error occurred during local copy: {e}")


""" 
ADDED 2025/12/25
"""

def dump_postgres_to_json_to_nas():
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"db_backup_{timestamp}.json"
    backup_path = os.path.join(NAS_BACKUP_DIR, filename)

    try:
        os.makedirs(NAS_BACKUP_DIR, exist_ok=True)

        with open(backup_path, "w") as f:
            subprocess.run(
                ["python", "manage.py", "dumpdata",
                 "--natural-primary", "--natural-foreign", "--indent", "2"],
                cwd="/invoice",
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )

        return backup_path

    except subprocess.CalledProcessError as e:
        raise Exception(f"Subprocess failed: {e.stderr}")