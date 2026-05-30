/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./**/*.px", "./app.py", "../../cms/**/*.px"],
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
