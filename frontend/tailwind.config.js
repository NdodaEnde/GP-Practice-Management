/** @type {import('tailwindcss').Config} */
//
// Clinical Integrity design tokens — pinned from the Type C mockup
// (Complete Doctor Suite/*.html `<script id="tailwind-config">`).
//
// Strategy: keep shadcn's HSL-CSS-var pattern for `primary`, `secondary`,
// `background`, `border` (so existing shadcn primitives stay consistent),
// and ADD the rest of the M3 palette + radius/spacing/typography tokens
// as plain Tailwind extensions. Theme.extend means legacy non-Type-C pages
// keep all Tailwind defaults.
//
module.exports = {
    darkMode: ["class"],
    content: [
        "./src/**/*.{js,jsx,ts,tsx}",
        "./public/index.html",
    ],
    theme: {
        extend: {
            // ---------------------------------------------------------------
            // Colors — full M3 palette from the Type C mockup
            // ---------------------------------------------------------------
            colors: {
                // shadcn-managed via CSS vars (re-pointed to mockup hex)
                background: 'hsl(var(--background))',
                foreground: 'hsl(var(--foreground))',
                card: {
                    DEFAULT:    'hsl(var(--card))',
                    foreground: 'hsl(var(--card-foreground))',
                },
                popover: {
                    DEFAULT:    'hsl(var(--popover))',
                    foreground: 'hsl(var(--popover-foreground))',
                },
                primary: {
                    DEFAULT:    'hsl(var(--primary))',
                    foreground: 'hsl(var(--primary-foreground))',
                },
                secondary: {
                    DEFAULT:    'hsl(var(--secondary))',
                    foreground: 'hsl(var(--secondary-foreground))',
                },
                muted: {
                    DEFAULT:    'hsl(var(--muted))',
                    foreground: 'hsl(var(--muted-foreground))',
                },
                accent: {
                    DEFAULT:    'hsl(var(--accent))',
                    foreground: 'hsl(var(--accent-foreground))',
                },
                destructive: {
                    DEFAULT:    'hsl(var(--destructive))',
                    foreground: 'hsl(var(--destructive-foreground))',
                },
                border: 'hsl(var(--border))',
                input:  'hsl(var(--input))',
                ring:   'hsl(var(--ring))',
                chart: {
                    '1': 'hsl(var(--chart-1))',
                    '2': 'hsl(var(--chart-2))',
                    '3': 'hsl(var(--chart-3))',
                    '4': 'hsl(var(--chart-4))',
                    '5': 'hsl(var(--chart-5))',
                },

                // M3 mockup tokens — referenced directly via classes like
                // `bg-surface-container-lowest`, `text-on-surface`, etc.
                'on-tertiary-fixed-variant': '#224583',
                'on-primary-fixed-variant':  '#00468c',
                'on-background':             '#191c1d',
                'surface-variant':           '#e1e3e4',
                'surface-container-low':     '#f2f4f5',
                'on-primary-container':      '#c8daff',
                'on-error-container':        '#93000a',
                'error-container':           '#ffdad6',
                'secondary-fixed':           '#90f4e8',
                'surface':                   '#f8f9fa',
                'surface-container-high':    '#e7e8e9',
                'error':                     '#ba1a1a',
                'surface-dim':               '#d8dadb',
                'on-secondary-container':    '#007169',
                'outline':                   '#727783',
                'primary-fixed-dim':         '#a9c7ff',
                'surface-container':         '#eceeef',
                'tertiary':                  '#224683',
                'tertiary-fixed-dim':        '#aec6ff',
                'primary-fixed':             '#d6e3ff',
                'primary-container':         '#005eb8',
                'on-error':                  '#ffffff',
                'inverse-primary':           '#a9c7ff',
                'tertiary-fixed':            '#d8e2ff',
                'inverse-on-surface':        '#eff1f2',
                'secondary-fixed-dim':       '#73d7cc',
                'outline-variant':           '#c2c6d4',
                'surface-tint':              '#005db6',
                'on-primary-fixed':          '#001b3d',
                'inverse-surface':           '#2e3132',
                'on-surface':                '#191c1d',
                'on-secondary-fixed':        '#00201d',
                'on-tertiary-fixed':         '#001a42',
                'on-tertiary':               '#ffffff',
                'surface-bright':            '#f8f9fa',
                'on-tertiary-container':     '#cbd9ff',
                'on-secondary-fixed-variant':'#00504a',
                'on-secondary':              '#ffffff',
                'on-primary':                '#ffffff',
                'surface-container-lowest':  '#ffffff',
                'secondary-container':       '#90f4e8',
                'surface-container-highest': '#e1e3e4',
                'tertiary-container':        '#3d5e9d',
                'on-surface-variant':        '#424752',
            },

            // ---------------------------------------------------------------
            // Border radius — Clinical Integrity scale (small, conservative)
            // ---------------------------------------------------------------
            borderRadius: {
                DEFAULT: '0.125rem',
                sm:      'calc(var(--radius) - 4px)',
                md:      'calc(var(--radius) - 2px)',
                lg:      '0.25rem',
                xl:      '0.5rem',
                full:    '0.75rem',     // squircle, NOT a circle
            },

            // ---------------------------------------------------------------
            // Spacing — named tokens (xs/base/sm/md/lg/xl/gutter) the
            // mockup uses verbatim (e.g. `p-md`, `gap-lg`, `space-y-xl`).
            // Tailwind's numeric scale (`p-4`, `gap-6`) still works alongside.
            // ---------------------------------------------------------------
            spacing: {
                xs:                 '4px',
                base:               '8px',
                sm:                 '12px',
                md:                 '16px',
                gutter:             '16px',
                'container-margin': '16px',
                lg:                 '24px',
                xl:                 '32px',
            },

            // ---------------------------------------------------------------
            // Font family — `font-h1` / `font-body-md` aliases for the
            // mockup's typography pairing (Manrope headings, Public Sans body).
            // ---------------------------------------------------------------
            fontFamily: {
                h1:              ['Manrope', 'system-ui', 'sans-serif'],
                h2:              ['Manrope', 'system-ui', 'sans-serif'],
                h3:              ['Manrope', 'system-ui', 'sans-serif'],
                heading:         ['Manrope', 'system-ui', 'sans-serif'],
                'body-lg':       ['"Public Sans"', 'system-ui', 'sans-serif'],
                'body-md':       ['"Public Sans"', 'system-ui', 'sans-serif'],
                'body-sm':       ['"Public Sans"', 'system-ui', 'sans-serif'],
                'data-tabular':  ['"Public Sans"', 'system-ui', 'monospace'],
                'label-caps':    ['"Public Sans"', 'system-ui', 'sans-serif'],
            },

            // ---------------------------------------------------------------
            // Font size — typographic scale matching the mockup visuals.
            // [size, { lineHeight, letterSpacing?, fontWeight? }]
            // ---------------------------------------------------------------
            fontSize: {
                'h1':         ['2.25rem', { lineHeight: '1.15', letterSpacing: '-0.015em', fontWeight: '800' }],
                'h2':         ['1.5rem',  { lineHeight: '1.25', letterSpacing: '-0.01em',  fontWeight: '700' }],
                'h3':         ['1.125rem',{ lineHeight: '1.35',                            fontWeight: '600' }],
                'body-lg':    ['1rem',    { lineHeight: '1.6' }],
                'body-md':    ['0.9375rem',{ lineHeight: '1.55' }],
                'body-sm':    ['0.8125rem',{ lineHeight: '1.5' }],
                'label-caps': ['0.6875rem',{ lineHeight: '1.35', letterSpacing: '0.06em',  fontWeight: '700' }],
            },

            keyframes: {
                'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
                'accordion-up':   { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up':   'accordion-up 0.2s ease-out',
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
