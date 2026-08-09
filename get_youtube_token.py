import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# The SCOPES needed for YouTube upload
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def main():
    print("Starting YouTube OAuth Flow...")
    
    # Path to the client secrets file we just saved
    client_secrets_file = 'client_secrets.json'
    
    if not os.path.exists(client_secrets_file):
        print(f"Error: {client_secrets_file} not found!")
        return

    # Use the client_secrets.json file to identify the application requesting authorization.
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, 
        SCOPES
    )
    
    # This will open a browser window for you to log in
    # It starts a local server on port 8080 by default (which matches your redirect URI)
    print("\nA browser window should open automatically. If not, click the link that appears below.")
    print("Please log in with the Google Account that owns your YouTube channel.")
    
    # run_local_server() will automatically handle the redirect to http://localhost:8000/
    credentials = flow.run_local_server(port=8000, open_browser=False)
    
    # Extract the Refresh Token
    refresh_token = credentials.refresh_token
    
    if refresh_token:
        print("\n" + "="*50)
        print("SUCCESS! Here is your Refresh Token:")
        print("="*50)
        print(refresh_token)
        print("="*50)
        print("\nPlease copy this Refresh Token and save it.")
        
        # Optionally, save the full credentials to a file just in case
        with open('youtube_token.json', 'w') as f:
            f.write(credentials.to_json())
            print("Full token saved to youtube_token.json for reference.")
    else:
        print("\nAuthentication was successful, but NO REFRESH TOKEN was returned.")
        print("This usually happens if you've already authorized the app before.")
        print("To fix this, go to your Google Account Settings -> Data & Privacy -> Third-party apps with account access,")
        print("remove the app, and run this script again.")

if __name__ == '__main__':
    main()
