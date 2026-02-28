<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Gemini HA — Google Gemini for Home Assistant

A custom Home Assistant integration that adds a **conversation agent**, a **speech-to-text (STT)** entity, and a **text-to-speech (TTS)** entity powered by the [Google Gemini Live API](https://ai.google.dev/).

---

## Features

| Feature | Details |
|---|---|
| **Conversation agent** | Multi-turn dialogue with conversation history, HA entity control via tool calls |
| **Speech-to-text** | Transcribes audio using Gemini's audio-understanding model |
| **Text-to-speech** | Natural-sounding speech via the Gemini Live API with selectable voices |

---

## Prerequisites

- Home Assistant **2024.6** or newer
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier available)
- Internet access from your HA instance

---

## Installation

### Option A — HACS (recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Select **Integrations** → click the **⋮** menu in the top-right corner → **Custom repositories**.
3. Enter the repository URL `https://github.com/FinityEx/Ha_gemini` and choose category **Integration**, then click **Add**.
4. Search for **Gemini HA** in the HACS integrations list and click **Download**.
5. Restart Home Assistant.

### Option B — Manual

1. Download or clone this repository.
2. Copy the `custom_components/gemini_ha` folder into your Home Assistant configuration directory so the final path is:
   ```
   <config>/custom_components/gemini_ha/
   ```
3. Restart Home Assistant.

---

## Configuration

### Add the integration

1. Go to **Settings → Devices & Services** and click **+ Add Integration** in the bottom-right corner.
2. Search for **Gemini HA** and select it.
3. Enter your **Gemini API key** when prompted.  
   The integration will validate the key and create the three entities automatically.

### Options

After setup, click **Configure** on the Gemini HA card to adjust:

| Option | Default | Description |
|---|---|---|
| **Conversation model** | `gemini-2.0-flash-live-001` | Gemini model used by the conversation agent |
| **STT language** | `en-US` | Language the microphone input is expected in |
| **TTS voice** | `Zephyr` | Voice used for text-to-speech responses |

#### Supported STT languages

`en-US` · `de-DE` · `es-ES` · `fr-FR` · `it-IT` · `ja-JP` · `ko-KR` · `pt-BR` · `zh-CN`

#### Supported TTS voices

`Aoede` · `Charon` · `Fenrir` · `Kore` · `Leda` · `Orus` · `Puck` · `Zephyr`

---

## Using the entities

### Voice assistant / Assist pipeline

After setup, navigate to **Settings → Voice assistants** and create or edit an Assist pipeline:

- **Conversation agent** → select **Gemini Conversation**
- **Speech-to-text** → select **Gemini STT**
- **Text-to-speech** → select **Gemini TTS**

### TTS via action

```yaml
action: tts.speak
target:
  entity_id: tts.gemini_tts
data:
  media_player_entity_id: media_player.living_room
  message: "Say cheerfully: Have a wonderful day!"
  options:
    voice: Aoede
```

### Conversation via action

```yaml
action: conversation.process
data:
  agent_id: conversation.gemini_conversation
  text: "Turn off the kitchen lights"
```

---

## Enabling debug logging

Add the following to your `configuration.yaml` to get detailed logs for diagnosing issues:

```yaml
logger:
  logs:
    custom_components.gemini_ha: debug
```

Restart Home Assistant after saving. Logs will appear in **Settings → System → Logs**.

---

## Versioning

This integration follows semantic versioning (`MAJOR.MINOR.PATCH`).  
The current version is **1.1.0**.  
Config-entry schema changes are tracked via HA's `VERSION` / `MINOR_VERSION` mechanism, so existing entries are migrated automatically without requiring re-setup.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Failed to connect" during setup | Invalid or revoked API key | Re-generate the key at [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| STT returns no transcript | Unsupported audio format or empty stream | Ensure your voice pipeline uses 16-bit PCM, 16 kHz, mono |
| TTS returns no audio | Live API quota exceeded or network error | Check HA logs; try again after a short delay |
| Conversation agent doesn't control devices | Entities not exposed to Assist | Go to **Settings → Voice assistants → Expose** and expose the relevant entities |

---

## Links

- [Issue tracker](https://github.com/FinityEx/Ha_gemini/issues)
- [Google Gemini API documentation](https://ai.google.dev/gemini-api/docs)
- [Gemini API key](https://aistudio.google.com/app/apikey)
