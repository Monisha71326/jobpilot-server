/*
 * JobPilot autofill engine. Injected into the current tab ONLY when you press "Fill this page".
 *
 * Hard safety rules (do not relax):
 *  - never clicks, submits or triggers a form's submit; never navigates
 *  - never touches password, file, hidden, checkbox, radio, button/submit, captcha or disabled/readonly fields
 *  - never overwrites a value the person already typed
 *  - only fills the handful of profile fields it was given
 * Returns {filled:[keys], skipped:[keys], host}. Nothing leaves the page from here.
 */
(function () {
  const RULES = [
    // order matters: more specific first
    ["first_name", /\b(first|given|fore)[\s_-]*name\b|^fname$|^first$/i],
    ["last_name", /\b(last|sur|family)[\s_-]*name\b|^lname$|^last$/i],
    ["full_name", /^(full[\s_-]*)?name$|\bfull[\s_-]*name\b|\byour name\b|\bcandidate name\b/i],
    ["email", /e[-\s_]?mail/i],
    ["phone", /\b(phone|mobile|tel|telephone|contact number|cell)\b/i],
    ["linkedin", /linked[\s_-]?in/i],
    ["github", /git[\s_-]?hub/i],
    ["portfolio", /\b(portfolio|personal (web)?site|website|blog|url)\b/i],
    ["city", /^(city|town)$|\bcity\b/i],
    ["location", /\b(current )?(location|address|where are you (based|located))\b|\bcity.*(state|country)\b/i],
    ["notice_period_days", /notice[\s_-]*period/i],
    ["years_experience", /(years?|yrs?)[\s\S]{0,25}(experience|exp)\b|\btotal experience\b|\bexperience \(?years/i],
    ["headline", /\b(headline|current (job )?title|professional title|current role)\b/i],
    ["summary", /\b(summary|about (you|yourself)|tell us about yourself|professional summary)\b/i],
    ["cover_letter", /cover[\s_-]*letter|why (do you want|are you interested)|additional information|message to (the )?(hiring|recruiter)/i],
  ];
  const AUTOCOMPLETE = {
    "given-name": "first_name", "family-name": "last_name", name: "full_name", email: "email", tel: "phone",
    "address-level2": "city", "street-address": "location",
  };
  const BLOCK_TYPES = new Set(["password", "file", "hidden", "checkbox", "radio", "submit", "button", "reset", "image", "range", "color", "date", "datetime-local", "month", "week", "time"]);
  const BLOCK_WORDS = /captcha|recaptcha|hcaptcha|password|passcode|otp|one[-\s]?time|ssn|social security|aadhaar|aadhar|\bpan\b|passport|credit|card number|cvv|bank|iban|gender|race|ethnic|disab|veteran|religio|caste|marital|date of birth|\bdob\b|salary|compensation|expected ctc|current ctc/i;

  function visible(el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  }
  function labelText(el) {
    const parts = [];
    if (el.id) { try { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) parts.push(l.innerText); } catch (e) { /* ignore */ } }
    const wrap = el.closest("label"); if (wrap) parts.push(wrap.innerText);
    const lb = el.getAttribute("aria-labelledby");
    if (lb) lb.split(/\s+/).forEach((id) => { const n = document.getElementById(id); if (n) parts.push(n.innerText); });
    parts.push(el.getAttribute("aria-label") || "", el.placeholder || "", el.name || "", el.id || "", el.getAttribute("data-qa") || "");
    // nearest preceding label-like text inside the same field group (common in React forms)
    const group = el.closest("[class*=field],[class*=form-group],[class*=question],fieldset,li,div");
    if (group && group !== document.body) { const t = group.querySelector("label,legend,.label,[class*=label]"); if (t && t !== el) parts.push(t.innerText); }
    return parts.join(" ").replace(/[*:]/g, " ").replace(/\s+/g, " ").trim().slice(0, 200);
  }
  function keyFor(el) {
    const ac = (el.getAttribute("autocomplete") || "").split(" ").pop();
    if (AUTOCOMPLETE[ac]) return AUTOCOMPLETE[ac];
    const t = (el.type || "text").toLowerCase();
    if (t === "email") return "email";
    if (t === "tel") return "phone";
    const text = labelText(el);
    for (const [key, re] of RULES) if (re.test(text)) return key;
    return null;
  }
  function setValue(el, value) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    el.focus();
    setter.call(el, value); // native setter so React/Vue controlled inputs notice the change
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.blur();
  }

  window.__jobpilotFill = function (fields) {
    const filled = [], skipped = new Set(), used = new Set();
    const els = Array.from(document.querySelectorAll("input, textarea"));
    for (const el of els) {
      if (el.disabled || el.readOnly || !visible(el)) continue;
      const type = (el.type || "text").toLowerCase();
      if (BLOCK_TYPES.has(type)) continue;
      const text = labelText(el);
      if (BLOCK_WORDS.test(text) || BLOCK_WORDS.test(el.name || "") ) continue;
      if (el.value && el.value.trim()) continue; // never overwrite the person's own input
      let key = keyFor(el);
      if (!key || !(key in fields) || !fields[key]) continue;
      // one-per-key for single-value fields (avoid filling a "name" box twice by accident)
      if (used.has(key) && key !== "cover_letter") continue;
      if (key === "cover_letter" && !(el instanceof HTMLTextAreaElement)) continue;
      if (key === "summary" && !(el instanceof HTMLTextAreaElement)) continue;
      setValue(el, String(fields[key]));
      used.add(key); filled.push(key);
    }
    Object.keys(fields).forEach((k) => { if (!used.has(k) && k !== "cover_letter") skipped.add(k); });
    return { filled, skipped: Array.from(skipped), host: location.hostname };
  };
})();
