import { Type } from '@google/genai';

export const haTools = [{
  functionDeclarations: [
    {
      name: "turn_on_device",
      description: "Turn on a smart home device like a light or switch.",
      parameters: {
        type: Type.OBJECT,
        properties: {
          entity_id: { type: Type.STRING, description: "e.g., 'light.living_room' or 'light.kitchen'" }
        },
        required: ["entity_id"]
      }
    },
    {
      name: "turn_off_device",
      description: "Turn off a smart home device like a light or switch.",
      parameters: {
        type: Type.OBJECT,
        properties: {
          entity_id: { type: Type.STRING, description: "e.g., 'light.living_room' or 'light.kitchen'" }
        },
        required: ["entity_id"]
      }
    },
    {
      name: "set_temperature",
      description: "Set the temperature of a thermostat.",
      parameters: {
        type: Type.OBJECT,
        properties: {
          entity_id: { type: Type.STRING, description: "e.g., 'climate.living_room'" },
          temperature: { type: Type.NUMBER, description: "Target temperature in Fahrenheit" }
        },
        required: ["entity_id", "temperature"]
      }
    },
    {
      name: "activate_scene",
      description: "Activate a smart home scene.",
      parameters: {
        type: Type.OBJECT,
        properties: {
          scene_id: { type: Type.STRING, description: "e.g., 'scene.goodnight' or 'scene.movie_time'" }
        },
        required: ["scene_id"]
      }
    }
  ]
}];
