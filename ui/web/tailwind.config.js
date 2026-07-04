/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./**/*.px", "./**/*.py", "./app.py", "../../cms/**/*.px"],
  safelist: [
    { pattern: /^grid-cols-(?:[1-9]|1[0-2])$/ },
  ],
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
