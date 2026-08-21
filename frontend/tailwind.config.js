/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                slate: {
                    950: '#0A0F1D',
                    900: '#111827',
                    800: '#1F2937',
                },
                emerald: {
                    500: '#10B981',
                    600: '#059669',
                },
                amber: {
                    500: '#F59E0B',
                    600: '#D97706',
                }
            },
        },
    },
    plugins: [],
}
