// Starts the "Daily episode" GitHub workflow on time every night.
// GitHub's own scheduler delays/drops runs for small repos; Cloudflare's doesn't.
// Extra triggers are safe: the workflow skips if today's episode already exists.
const REPO = "Codedecoder1/last-night-on-sports";
const WORKFLOW = "daily-episode.yml";

async function startEpisode(env) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "lnos-scheduler",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  console.log("GitHub dispatch:", r.status, r.status === 204 ? "started" : await r.text());
  return r.status;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(startEpisode(env));
  },
};
