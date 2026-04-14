/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./home.px", "./report.py", "./layout.px", "./app.py"],
  theme: {
    extend: {
      colors: {
        brand: {
          header: "#4B5D06",
        },
        report: {
          accent: "#4B5D06",
          zebra: "#f4f6f0",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
