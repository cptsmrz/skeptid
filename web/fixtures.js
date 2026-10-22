/* Mock verdicts. Shape matches SPEC.md section 8 Verdict response exactly. */
window.SKEPTID_FIXTURES = {
  low: {
    id: "3a1c90e2-7b44-4c1a-9e2d-11aa22bb33cc",
    modality: "text",
    label: "safe",
    risk: 0.18,
    level: "LOW",
    confidence: 0.81,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "own", ok: true, risk: 0.18, model_version: "mock", latency_ms: 22 },
      { id: "opensource", ok: true, risk: 0.21, model_version: "mock", latency_ms: 41 },
      { id: "external", ok: true, risk: 0.16, model_version: "mock", latency_ms: 38 }
    ],
    evidence: [
      {
        kind: "span",
        description: "Routine maintenance notice",
        payload: { start: 63, end: 92, weight: 0.11 }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  medium: {
    id: "b7e4d012-91aa-4f88-8c21-0c9de441aa10",
    modality: "text",
    label: "spam",
    risk: 0.52,
    level: "MEDIUM",
    confidence: 0.64,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "own", ok: true, risk: 0.52, model_version: "mock", latency_ms: 19 },
      { id: "opensource", ok: true, risk: 0.48, model_version: "mock", latency_ms: 55 },
      { id: "external", ok: true, risk: 0.57, model_version: "mock", latency_ms: 44 }
    ],
    evidence: [
      {
        kind: "span",
        description: "Opt-out mailing language",
        payload: { start: 20, end: 30, weight: 0.22 }
      },
      {
        kind: "flag",
        description: "Unsolicited commercial phrasing",
        payload: { rule: "commercial_unsolicited" }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  high: {
    id: "e90f12ab-44c1-4d77-a118-9b0c3d5e6f70",
    modality: "text",
    label: "phishing",
    risk: 0.87,
    level: "HIGH",
    confidence: 0.74,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "own", ok: true, risk: 0.87, model_version: "mock", latency_ms: 41 },
      { id: "opensource", ok: true, risk: 0.81, model_version: "mock", latency_ms: 63 },
      { id: "external", ok: true, risk: 0.84, model_version: "mock", latency_ms: 52 }
    ],
    evidence: [
      {
        kind: "span",
        description: "Urgency + credential request",
        payload: { start: 0, end: 31, weight: 0.31 }
      },
      {
        kind: "span",
        description: "Password confirmation request",
        payload: { start: 59, end: 80, weight: 0.28 }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  disagree: {
    id: "c2aa1098-33d0-4b11-9e77-55a0bbccdde1",
    modality: "text",
    label: "phishing",
    risk: 0.71,
    level: "HIGH",
    confidence: 0.42,
    disagreement: true,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "own", ok: true, risk: 0.71, model_version: "mock", latency_ms: 27 },
      { id: "opensource", ok: true, risk: 0.22, model_version: "mock", latency_ms: 49 },
      { id: "external", ok: true, risk: 0.68, model_version: "mock", latency_ms: 58 }
    ],
    evidence: [
      {
        kind: "span",
        description: "Credential-trap payment link",
        payload: { start: 65, end: 77, weight: 0.29 }
      },
      {
        kind: "flag",
        description: "Provider risk spread above 0.40",
        payload: { rule: "disagreement" }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  partial: {
    id: "11d0aa32-8e91-4c02-b445-77ff0099aa22",
    modality: "text",
    label: "spam",
    risk: 0.46,
    level: "MEDIUM",
    confidence: 0.51,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "own", ok: true, risk: 0.46, model_version: "mock", latency_ms: 24 },
      { id: "opensource", ok: true, risk: 0.41, model_version: "mock", latency_ms: 71 },
      { id: "external", ok: false, risk: 0.0, model_version: "mock", latency_ms: 8000, error: "timeout" }
    ],
    evidence: [
      {
        kind: "flag",
        description: "Header path incomplete",
        payload: { check: "header", field: "Authentication-Results", issue: "Missing authentication results" }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  fail: {
    status: 503,
    detail: "All analysis providers failed. No verdict could be reliably formed."
  },
  email: {
    id: "98aa21c0-6d44-4e19-8f03-bb12cc34de56",
    modality: "email",
    label: "phishing",
    risk: 0.83,
    level: "HIGH",
    confidence: 0.69,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "own", ok: true, risk: 0.83, model_version: "mock", latency_ms: 36 },
      { id: "opensource", ok: true, risk: 0.77, model_version: "mock", latency_ms: 60 },
      { id: "external", ok: true, risk: 0.8, model_version: "mock", latency_ms: 47 }
    ],
    evidence: [
      {
        kind: "span",
        description: "Urgency around an attached invoice",
        payload: { start: 15, end: 31, weight: 0.24 }
      },
      {
        kind: "span",
        description: "Payment-page instruction",
        payload: { start: 47, end: 59, weight: 0.19 }
      },
      {
        kind: "flag",
        description: "IP-literal host",
        payload: {
          check: "url",
          display: "payment page",
          href: "http://192.0.2.44/pay",
          issue: "IP-literal host"
        }
      },
      {
        kind: "flag",
        description: "From vs Reply-To mismatch",
        payload: {
          check: "header",
          field: "Reply-To",
          issue: "From vs Reply-To mismatch"
        }
      },
      {
        kind: "flag",
        description: "Missing Authentication-Results",
        payload: {
          check: "header",
          field: "Authentication-Results",
          issue: "No SPF/DKIM/DMARC result present"
        }
      },
      {
        kind: "metric",
        description: "Attachment needs review",
        payload: {
          check: "attachment",
          filename: "invoice.png",
          type: "image/png",
          size: 48210,
          risk: 0.72
        }
      },
      {
        kind: "metric",
        description: "Listed attachment",
        payload: {
          check: "attachment",
          filename: "terms.txt",
          type: "text/plain",
          size: 1204,
          risk: 0.08
        }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  image: {
    id: "44bb09de-1a22-4c90-9f11-aa00bb11cc22",
    modality: "image",
    label: "ai_edited",
    risk: 0.61,
    level: "MEDIUM",
    confidence: 0.58,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "external", ok: true, risk: 0.59, model_version: "mock", latency_ms: 112 },
      { id: "opensource", ok: true, risk: 0.55, model_version: "mock", latency_ms: 88 },
      { id: "own", ok: true, risk: 0.61, model_version: "mock", latency_ms: 47 }
    ],
    evidence: [
      {
        kind: "heatmap",
        description: "Forensic anomaly map (synthetic mock example)",
        payload: { png_b64: "iVBORw0KGgoAAAANSUhEUgAAAGAAAABACAYAAADlNHIOAAADZ0lEQVR4nO2b604iQRCFfZD+CaKICyy6DQuKgorrBUXU6GaTfdN+ts0kp5KTDksMM1CddP34MhdulXOqTnMZ9oJ3e4Ye6gXkjnoBuaNeQO6oF5A76gXkjnoBuaNeQO6oF5A76gXkjnoBuaNewI6pBe/qxH50XDMDqkeELmgE7w6Iw+i4QfetmwHVCN8gsZvBuyOiFR03yZTGLozQFmkb1Eh4Fr0Q+zh4941oR8fHZIqYIUZsJZ60xaqaOnV8MxK9ELsTvOsS36PjDpkiZjRpIiqfBm3BtiH+ITpYhO+Q2L3g3QlxGh33yJQOGXFE01CpCdqibVP8NgkvYv8AHvRpX24TU8SI9jZN0BauavFb1PXS8SJ8IfYA/ARD2pfb+mSETIRMQ6tqE7TFK0st6nwW/4S6fUCCj4J3Z+Cc9kdkyICm4iQygSeh9MKsLWBZ9rFASuzE4vch6IgEHwfvLsAl7Y/JkBEe119hgsTRAV4/WwMkepqU+f8T/5wEnwTvpuCK9idkyPkaE2RNaFYRRdoilu1+zv0uMpvFP0Nni/CF4NfBuxswo/1r3C5GjPF4NqGH1+H1oNQUaItYVfdL9Jwiu6XzRfwpCX8bvPsF7mj/loyYkgkyCR7Pz1FUegq0hSzT/Qe08HYpegYUOyz+jER/AI+0L2bMIhMkjgYURV1akEutBdpCljFA4qdN3c/Rc4E4YfHvIfo8ePcUvHvGdo7z95EJEzwPR9EprQWlY0hbyE2orYifHnX/kLr/CrEi4s8h+iJ49xK8W2K7wPk5mXCDx8sUDGkKeitiaKO3pNpibkL9C/Ezpu6/Rbw8QuRC8Nfg3Vvw7h3bV5x/xv3u8DiZgvEXYmijdUBbzCoN8FH8TKn7H9DdC4hdCP8RvPvE9h3nF7jfA03BNIohbwZsZsATuvwNov8O3v3B9gPnX3A/M2AN6xbgOP9nUfws0e2fEP8vtp84v4xiaLZiHah0IdYW0yYgAUF3ZYCtAVs2wN4F7Qj7HJAA9kk4AQPsuyBF7NvQBLDfAxKbAvtFTGkK7DdhReyqiASw64ISwK6MSwC7NjQB7OroBLD/BySC/UMmEew/Yglh/5I0zICkUC8gd9QLyB31AnJHvYDcUS8gd9QLyB31AnJHvYDcUS8gd9QLyB31AnJHvYDc+QffWp2Gw5syAgAAAABJRU5ErkJggg==" }
      },
      {
        kind: "metric",
        description: "ELA block energy",
        payload: { name: "ela_energy", value: 0.44 }
      }
    ],
    limits_note: "Risk score with evidence, not proof."
  },
  video: {
    id: "77cc18ef-2b33-4d01-8012-bb11cc22dd33",
    modality: "video",
    label: "filtered",
    risk: 0.39,
    level: "MEDIUM",
    confidence: 0.62,
    disagreement: false,
    primary_provider: "own",
    mock: true,
    providers: [
      { id: "external", ok: true, risk: 0.41, model_version: "mock", latency_ms: 210 },
      { id: "opensource", ok: true, risk: 0.33, model_version: "mock", latency_ms: 176 },
      { id: "own", ok: true, risk: 0.39, model_version: "mock", latency_ms: 94 }
    ],
    evidence: [
      { kind: "frame_score", description: "Frame risk", payload: { t: 0.0, score: 0.21 } },
      { kind: "frame_score", description: "Frame risk", payload: { t: 0.8, score: 0.28 } },
      { kind: "frame_score", description: "Frame risk", payload: { t: 1.6, score: 0.47 } },
      { kind: "frame_score", description: "Frame risk", payload: { t: 2.4, score: 0.52 } },
      { kind: "frame_score", description: "Frame risk", payload: { t: 3.2, score: 0.31 } },
      { kind: "heatmap", description: "Highest-risk frame anomaly map", payload: { png_b64: "", t: 2.4 } }
    ],
    limits_note: "Risk score with evidence, not proof."
  }
};

window.SKEPTID_SAMPLES = {
  low: "IT notice: the office network will restart at 22:00 on Friday. No password or account action is required.",
  medium: "Weekend deals only. Reply STOP to this mailing. Limited stock on last season cables and chargers.",
  high: "Urgent: verify your account now. Open the sign-in page and confirm your password before we close the account.",
  disagree: "The attached statement looks ordinary. A second scan flagged the payment link as a credential trap.",
  partial: "Can you review this vendor message? The body is short and the header path is incomplete.",
  fail: "FORCE_PROVIDER_FAILURE",
  email: "Please pay the attached invoice today. Use the payment page to avoid suspension of the account."
};
