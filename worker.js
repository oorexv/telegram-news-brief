// Cloudflare Worker: relays Telegram replies to instant news-brief summaries.
//
// One-time setup after deploying:
//   1. In the Worker's settings, add an environment variable/secret named
//      TELEGRAM_BOT_TOKEN with your bot's token.
//   2. Visit https://<your-worker>.workers.dev/register once in a browser.
//      That registers this Worker as the bot's webhook.
//   3. Reply to any brief in Telegram with a number 1-6 to test.

const STATE_URL =
  "https://raw.githubusercontent.com/oorexv/telegram-news-brief/main/state.json";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/register") {
      const webhookUrl = `${url.origin}/webhook`;
      const setUrl = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/setWebhook?url=${encodeURIComponent(
        webhookUrl
      )}`;
      const res = await fetch(setUrl);
      const data = await res.json();
      return new Response(JSON.stringify(data, null, 2), {
        headers: { "content-type": "application/json" },
      });
    }

    if (url.pathname === "/webhook" && request.method === "POST") {
      try {
        const update = await request.json();
        const msg = update.message;
        if (msg && typeof msg.text === "string") {
          const num = msg.text.trim();
          if (/^[1-6]$/.test(num)) {
            await handleNumberReply(env, msg.chat.id, num);
          }
        }
      } catch (e) {
        // swallow errors so Telegram doesn't retry forever on a bad payload
        console.log("webhook error", e);
      }
      return new Response("ok");
    }

    return new Response("News brief relay is running.");
  },
};

async function handleNumberReply(env, chatId, num) {
  let state;
  try {
    const res = await fetch(`${STATE_URL}?t=${Date.now()}`, {
      cf: { cacheTtl: 0, cacheEverything: false },
    });
    state = await res.json();
  } catch (e) {
    await sendMessage(
      env,
      chatId,
      "Couldn't load the latest brief right now — try again in a bit."
    );
    return;
  }

  const item = state.items && state.items[num];
  if (!item) {
    await sendMessage(
      env,
      chatId,
      "That number isn't in the current brief. Wait for the next one!"
    );
    return;
  }

  const text = `${item.title}\n\n${item.summary}\n\n🔗 Read full article: ${item.link}`;
  await sendMessage(env, chatId, text);
}

async function sendMessage(env, chatId, text) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}
