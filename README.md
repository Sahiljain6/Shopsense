# ShopSense Chatbot

A simple static HTML chatbot website that can be deployed on GitHub Pages.

## Files

- `index.html` - the page structure.
- `styles.css` - the responsive design.
- `script.js` - the chatbot logic and API call.

## Use locally

Open `index.html` in your browser. You can chat immediately in demo mode.

To test live AI replies:

1. Paste an API key into the **API key** field.
2. Keep the endpoint as `https://api.openai.com/v1/chat/completions`, or replace it with your own proxy URL.
3. Click **Save settings**.
4. Send a chat message.

> Important: GitHub Pages is public. Do not hard-code a real secret key in this repo. For production, deploy a small backend/proxy that keeps the key on the server.

## Deploy to GitHub Pages

1. Push this repository to GitHub.
2. Open **Settings → Pages**.
3. Set **Source** to **Deploy from a branch**.
4. Select your branch and the repository root folder.
5. Save, then open the GitHub Pages URL after deployment finishes.
