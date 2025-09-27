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

def copy_to_nas():
    """Copies the latest local backup to the NAS directory."""

    local_backup_path = _find_latest_local_backup_path()

    if local_backup_path is None or not os.path.exists(local_backup_path):
        # This is not a critical error, but indicates the first step wasn't run
        # or the file was deleted.
        raise FileNotFoundError("No local backup found to copy. Please run 'Copy Local DB' first.")

    # Ensure NAS backup directory exists (this might fail if NAS is not accessible/writable)
    try:
        os.makedirs(NAS_BACKUP_DIR, exist_ok=True)
    except OSError as e:
         raise OSError(f"Cannot create/access NAS directory {NAS_BACKUP_DIR}. Check path and permissions: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred checking NAS directory: {e}")

    try:
        # Get the filename from the local backup path
        backup_filename = os.path.basename(local_backup_path)

        # Construct the full path for the NAS copy
        nas_copy_path = os.path.join(NAS_BACKUP_DIR, backup_filename)

        # Perform the copy to NAS
        shutil.copy2(local_backup_path, nas_copy_path)

        return nas_copy_path # Return the path of the NAS copy

    except FileNotFoundError:
         # This specific FileNotFoundError is less likely now that we check exists() above,
         # but kept for completeness if something changes between check and copy.
         raise FileNotFoundError(f"Local backup file not found during copy or NAS path is incorrect.")
    except PermissionError:
        raise PermissionError(f"Permission denied. Cannot write to {NAS_BACKUP_DIR}. Check NAS access.")
    except Exception as e:
        raise Exception(f"An error occurred during NAS copy: {e}")


def dump_postgres_to_json():    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"db_backup_{timestamp}.json"
    backup_dir = NAS_BACKUP_DIR   
    backup_path = os.path.join(backup_dir, filename)

    try:
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)

        with open(backup_path, "w") as f:
            result = subprocess.run(
                ["python", "manage.py", "dumpdata", "--natural-primary", "--natural-foreign", "--indent", "2"],
                cwd="/invoice", 
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        
        # Confirm file was created
        if not os.path.isfile(backup_path):
            raise FileNotFoundError(f"Backup file was not created: {backup_path}")

        return backup_path

    except subprocess.CalledProcessError as e:
        raise Exception(f"Subprocess failed: {e.stderr}")
    except Exception as e:
        raise Exception(f"Failed to create backup: {e}")