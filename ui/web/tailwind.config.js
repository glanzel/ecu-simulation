/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./home.px", "./report.px", "./app.py"],
  theme: {
    extend: {
      colors: {
        report: {
          accent: "#60CBEB",
          zebra: "#F5F5F5",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
