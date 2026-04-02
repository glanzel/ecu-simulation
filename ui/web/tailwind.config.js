/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./home.px", "./report.px", "./app.py"],
  theme: {
    extend: {},
  },
  plugins: [require("@tailwindcss/typography")],
};
