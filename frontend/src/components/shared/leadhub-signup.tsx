"use client";

import { ChangeEvent, FormEvent, useState } from "react";
import { ArrowRight } from "lucide-react";
import { useLanguage } from "@/providers/language-provider";

const leadHubOrigin = (() => {
  try {
    const url = new URL(process.env.NEXT_PUBLIC_LEADHUB_URL || "");
    return url.protocol === "https:" && !url.username && !url.password ? url.origin : "";
  } catch {
    return "";
  }
})();

export function LeadHubSignup() {
  const { t } = useLanguage();
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [recommendations, setRecommendations] = useState<Array<{ id: string; name: string; url: string; reason: string }>>([]);
  const [recommendationStatus, setRecommendationStatus] = useState("");

  if (!leadHubOrigin) return null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setSubmitting(true);
    setStatus("");
    try {
      const response = await fetch(`${leadHubOrigin}/api/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: "kisansetu",
          email: fields.get("email"),
          consent: fields.get("consent") === "on",
          website: fields.get("website"),
          source: window.location.hostname,
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "Signup failed");
      form.reset();
      setStatus(result.message || t("landing.leadSuccess"));
    } catch {
      setStatus(t("landing.leadError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRecommendations(event: ChangeEvent<HTMLInputElement>) {
    const checkbox = event.currentTarget;
    setRecommendations([]);
    setRecommendationStatus(checkbox.checked ? t("landing.relatedLoading") : "");
    if (!checkbox.checked) return;
    try {
      const response = await fetch(`${leadHubOrigin}/api/recommendations?project=kisansetu&consent=true`);
      const result = await response.json();
      if (!response.ok) throw new Error("Suggestions unavailable");
      if (checkbox.checked) {
        setRecommendations(result.items || []);
        setRecommendationStatus(result.items?.length ? "" : t("landing.relatedEmpty"));
      }
    } catch {
      if (checkbox.checked) setRecommendationStatus(t("landing.relatedUnavailable"));
    }
  }

  return (
    <section className="landing-leadhub" aria-labelledby="landing-leadhub-title">
      <p className="landing-eyebrow">{t("landing.leadEyebrow")}</p>
      <h2 id="landing-leadhub-title">{t("landing.leadTitle")}</h2>
      <p>{t("landing.leadBody")}</p>
      <form className="landing-leadhub-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="landing-leadhub-email">{t("landing.leadEmail")}</label>
        <input id="landing-leadhub-email" name="email" type="email" autoComplete="email" maxLength={254} placeholder={t("landing.leadEmail")} required />
        <label className="landing-leadhub-consent"><input name="consent" type="checkbox" required />{t("landing.leadConsent")}</label>
        <label className="landing-leadhub-consent"><input type="checkbox" onChange={handleRecommendations} />{t("landing.relatedConsent")}</label>
        <div className="landing-leadhub-honeypot" aria-hidden="true"><label htmlFor="landing-leadhub-website">Leave empty</label><input id="landing-leadhub-website" name="website" tabIndex={-1} autoComplete="off" /></div>
        <button type="submit" disabled={submitting}>{t("landing.leadSubmit")}<ArrowRight size={15} aria-hidden="true" /></button>
        <p className="landing-leadhub-status" role="status" aria-live="polite">{status}</p>
      </form>
      <div className="landing-leadhub-recommendations" aria-live="polite">
        {recommendationStatus && <p>{recommendationStatus}</p>}
        {recommendations.length > 0 && <><h3>{t("landing.relatedTitle")}</h3><ul>{recommendations.map((item) => <li key={item.id}><a href={item.url} target="_blank" rel="noopener noreferrer">{item.name}</a><span> — {item.reason}</span></li>)}</ul></>}
      </div>
    </section>
  );
}
