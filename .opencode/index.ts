export { ECCHooksPlugin, default } from "./plugins/index.js"
export * from "./plugins/index.js"

export const VERSION = "1.0.0"

export const metadata = {
  name: "ecc-clv2",
  version: VERSION,
  description: "Continuous Learning v2 for OpenCode",
  author: "stripped-from-ecc",
  features: {
    commands: 10,
    skills: 1,
    hookEvents: [
      "tool.execute.before",
      "tool.execute.after",
      "session.created",
      "session.idle",
      "session.deleted",
    ],
  },
}
