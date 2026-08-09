# Facebook API Setup Guide

## 🔑 Facebook App Kaise Banaye

### Step 1: Facebook Developer Account Banao

1. **https://developers.facebook.com** pe jao
2. Apne Facebook account se login karo
3. **"My Apps"** → **"Create App"** pe click karo
4. App type select karo: **"Business"**
5. App name daalo: `"FIFA World Cup Video Bot"`
6. **"Create App"** pe click karo

### Step 2: App Permissions Add Karo

App Dashboard mein jao → **"App Settings"** → **"Basic"**:

1. **"Add Product"** pe click karo
2. **"Facebook Login"** select karo
3. Valid OAuth Redirect URIs mein daalo: `https://localhost/`

### Step 3: Pages Access Token Generate Karo

#### Method 1: Graph API Explorer (Recommended)

1. **https://developers.facebook.com/tools/explorer/** pe jao
2. Top-right mein apna App select karo
3. **"Generate Access Token"** pe click karo
4. Ye permissions select karo:
   - ✅ `pages_show_list`
   - ✅ `pages_read_engagement`
   - ✅ `pages_manage_posts`
   - ✅ `pages_read_user_content`
   - ✅ `publish_video`
   - ✅ `publish_to_groups`
5. **"Generate Access Token"** pe click karo
6. Token copy karo — ye **User Access Token** hai

#### Step 4: Page Access Token Lelo

Graph API Explorer mein ye URL daalo:

```
GET /me/accounts?limit=100
```

Response mein tumhara page dikhega:
```json
{
  "data": [
    {
      "id": "YOUR_PAGE_ID",
      "name": "Your Page Name",
      "access_token": "PAGE_ACCESS_TOKEN"
    }
  ]
}
```

- `id` → ye tumhara **FB_PAGE_ID** hai
- `access_token` → ye tumhara **FB_ACCESS_TOKEN** hai

### Step 5: Token Ko Long-Lived Banao (Important!)

User Access Token sirf 1-2 hours live rehta hai. Isko long-lived banao:

```
GET /oauth/access_token?
  grant_type=fb_exchange_token&
  client_id=YOUR_APP_ID&
  client_secret=YOUR_APP_SECRET&
  fb_exchange_token=YOUR_SHORT_LIVED_TOKEN
```

Response:
```json
{
  "access_token": "LONG_LIVED_TOKEN",
  "token_type": "bearer",
  "expires_in": 5184000
}
```

Ye token **60 days** tak live rahega!

### Step 6: Page Token Ko Infinite Banao

Page Access Token automatically renew hota hai agar:
- App approved hai (Live status)
- User ne app ko authorize kiya hai

Agar app development mode mein hai toh sirf tumhe dikhega.

---

## 🔧 GitHub Secrets Kaise Set Karo

GitHub repo mein jao → **Settings** → **Secrets and variables** → **Actions**:

| Secret Name | Value |
|-------------|-------|
| `FB_ACCESS_TOKEN` | Page Access Token (long-lived) |
| `FB_PAGE_ID` | Page ID (numbers only) |

---

## 🧪 Token Test Karne Ka Tarika

### Quick Test (Browser)

Ye URL browser mein open karo (token aur page_id daal ke):

```
https://graph.facebook.com/v19.0/me?access_token=YOUR_TOKEN
```

Agar `{"name": "Your Name", "id": "123456"}` aaye toh token valid hai!

### Page Access Test

```
https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_TOKEN
```

Apna page dikhna chahiye response mein.

### Upload Test (Python Script)

```python
import os
import requests

# Token set karo
ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN"
PAGE_ID = "YOUR_PAGE_ID"

# Step 1: Initialize upload
url = f"https://graph.facebook.com/v19.0/{PAGE_ID}/video_reels"
payload = {
    'access_token': ACCESS_TOKEN,
    'upload_phase': 'start',
    'file_size': 1024  # dummy size
}
response = requests.post(url, data=payload)
print("Init:", response.json())
```

---

## ⚠️ Common Errors

| Error | Meaning | Fix |
|-------|---------|-----|
| `Invalid access token` | Token expire ho gaya | Naya token generate karo |
| `Error validating access token` | Token invalid hai | Long-lived token banao |
| `(#10) Pages manage posts permission required` | Permission missing | App permissions mein `pages_manage_posts` add karo |
| `Rate limit reached` | Bahut zyada API calls | Kuch der wait karo |
| `OAuthException: Invalid OAuth access token` | Token galat hai | Graph Explorer se naya token lo |

---

## 📋 Checklist

- [ ] Facebook Developer Account banao
- [ ] App create karo (Business type)
- [ ] Facebook Login product add karo
- [ ] Graph API Explorer se token generate karo
- [ ] Required permissions select karo
- [ ] Page Access Token lo
- [ ] Token ko long-lived banao
- [ ] GitHub Secrets set karo (FB_ACCESS_TOKEN, FB_PAGE_ID)
- [ ] Token test karo (browser URL se)
- [ ] Pipeline run karo
