import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0d1320",
        surface: "#0d1320",
        "surface-container-lowest": "#070e1a",
        "surface-container-low": "#151c28",
        "surface-container": "#19202c",
        "surface-container-high": "#232a37",
        "surface-container-highest": "#2e3542",
        "on-surface": "#dce2f4",
        "on-surface-variant": "#bfc7d2",
        primary: "#97cbff",
        "primary-container": "#4dabf7",
        "on-primary-container": "#003d64",
        "on-primary": "#003354",
        tertiary: "#ffb95f",
        "tertiary-container": "#e59300",
        outline: "#89919c",
        "outline-variant": "#404751",
        error: "#ffb4ab",
        "error-container": "#93000a",
      },
      maxWidth: {
        chat: "800px",
      },
      spacing: {
        "bubble-x": "16px",
        "bubble-y": "12px",
        "chat-gap": "12px",
      },
    },
  },
  plugins: [],
};

export default config;
