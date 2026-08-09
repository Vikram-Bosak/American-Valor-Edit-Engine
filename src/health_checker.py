import os
import socket
import requests
try:
    from .logger import logger
except ImportError:
    from logger import logger

def check_internet(timeout=5):
    """
    Checks if there is an active internet connection.
    Uses per-socket timeout instead of global setdefaulttimeout to avoid
    polluting process-wide socket state.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("8.8.8.8", 53))
        return True, "Internet connection is active."
    except Exception as e:
        return False, f"Internet connection check failed: {e}"
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass

def check_facebook_token(access_token, page_id):
    """
    Verifies if the Facebook access token is valid and has access to the page.
    Also checks for the 'pages_manage_posts' permission needed for uploads.
    """
    if not access_token or not page_id:
        return False, "Facebook credentials (access token or page ID) are missing from configuration."
        
    url = f"https://graph.facebook.com/v19.0/me?access_token={access_token}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Check token expiry via debug_token endpoint
            debug_url = f"https://graph.facebook.com/v19.0/debug_token?input_token={access_token}&access_token={access_token}"
            try:
                debug_resp = requests.get(debug_url, timeout=10)
                if debug_resp.status_code == 200:
                    token_info = debug_resp.json().get('data', {})
                    expires_at = token_info.get('expires_at', 0)
                    if expires_at > 0:
                        import time
                        remaining = expires_at - int(time.time())
                        if remaining <= 0:
                            return False, "Facebook access token has expired. Generate a fresh token."
                        elif remaining < 3600:
                            from logger import logger
                            logger.warning(f"Facebook access token expires in {remaining} seconds (~{remaining//60} min). Consider refreshing soon.")
            except Exception:
                pass  # debug_token is best-effort

            accounts_url = f"https://graph.facebook.com/v19.0/me/accounts?limit=100&access_token={access_token}"
            acc_resp = requests.get(accounts_url, timeout=10)
            if acc_resp.status_code == 200:
                pages = acc_resp.json().get('data', [])
                for page in pages:
                    if str(page.get('id')) == str(page_id):
                        # Verify the page token has pages_manage_posts permission
                        page_token = page.get('access_token', '')
                        if page_token:
                            perm_url = f"https://graph.facebook.com/v19.0/me/permissions?access_token={page_token}"
                            try:
                                perm_resp = requests.get(perm_url, timeout=10)
                                if perm_resp.status_code == 200:
                                    perms = perm_resp.json().get('data', [])
                                    granted = {p.get('permission') for p in perms if p.get('status') == 'granted'}
                                    required = {'pages_manage_posts', 'pages_read_engagement'}
                                    missing = required - granted
                                    if missing:
                                        return False, (
                                            f"Facebook token valid for page '{page.get('name')}' ({page_id}), "
                                            f"but missing required permissions: {', '.join(sorted(missing))}. "
                                            f"Re-authorize at https://developers.facebook.com/tools/explorer/ "
                                            f"with 'pages_manage_posts' and 'pages_read_engagement' permissions."
                                        )
                            except Exception:
                                pass  # permission check is best-effort
                        return True, f"Facebook API connection successful. Verified access to page: {page.get('name')} ({page_id})"
                return False, f"Facebook API connection successful, but target Page ID {page_id} was not found in user accounts."
            else:
                err_msg = ""
                try:
                    err_data = acc_resp.json()
                    err_msg = err_data.get('error', {}).get('message', '')
                except Exception:
                    pass
                return False, f"Facebook API reachable, but failed to query page accounts: {err_msg or acc_resp.text}"
        else:
            try:
                err_data = response.json()
                err_msg = err_data.get('error', {}).get('message', 'Unknown error')
                err_code = err_data.get('error', {}).get('code', 'unknown')
                err_subcode = err_data.get('error', {}).get('error_subcode', 'unknown')
                # Provide specific guidance
                hint = ""
                if response.status_code == 401 or err_code == 190:
                    hint = " The token is expired or revoked."
                elif response.status_code == 403:
                    hint = " The token lacks required permissions."
                return False, f"Facebook token validation failed: {err_msg} (code: {err_code}, subcode: {err_subcode}){hint}"
            except Exception:
                return False, f"Facebook token validation failed with status {response.status_code}: {response.text}"
    except requests.exceptions.Timeout:
        return False, "Facebook API connection timed out. Check network connectivity."
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Facebook API. Check network/firewall settings."
    except Exception as e:
        return False, f"Failed to connect to Facebook API: {e}"

def check_google_drive():
    """
    Checks if Google Drive service can connect and access the root folder.
    """
    try:
        try:
            from .drive_reader import get_drive_service
        except ImportError:
            from drive_reader import get_drive_service
            
        service = get_drive_service()
        root_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')
        if not root_folder_id:
            return False, "GOOGLE_DRIVE_FOLDER_ID is missing from configuration."
            
        # Try to retrieve metadata for the root folder to verify connection/access
        folder = service.files().get(fileId=root_folder_id, fields="id, name").execute()
        return True, f"Google Drive API connection successful. Connected to folder: {folder.get('name')}"
    except Exception as e:
        return False, f"Google Drive connection check failed: {e}"

def run_all_health_checks(access_token, page_id):
    """
    Runs all health checks and returns (is_healthy, status_results).
    """
    logger.info("Running system health checks...")
    results = {}
    is_healthy = True
    
    # Run Internet check
    ok, msg = check_internet()
    results["Internet"] = {"ok": ok, "message": msg}
    if not ok:
        is_healthy = False
        logger.error(f"Health Check Failed: {msg}")
    else:
        logger.info(f"Health Check Passed: {msg}")
        
    # Run Google Drive check
    ok, msg = check_google_drive()
    results["Google Drive"] = {"ok": ok, "message": msg}
    if not ok:
        is_healthy = False
        logger.error(f"Health Check Failed: {msg}")
    else:
        logger.info(f"Health Check Passed: {msg}")
        
    # Run Facebook check
    ok, msg = check_facebook_token(access_token, page_id)
    results["Facebook"] = {"ok": ok, "message": msg}
    if not ok:
        is_healthy = False
        logger.error(f"Health Check Failed: {msg}")
    else:
        logger.info(f"Health Check Passed: {msg}")
        
    return is_healthy, results
