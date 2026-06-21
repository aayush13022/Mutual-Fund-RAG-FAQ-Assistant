---
name: Compliance-First Dark
colors:
  surface: '#0d1320'
  surface-dim: '#0d1320'
  surface-bright: '#333947'
  surface-container-lowest: '#070e1a'
  surface-container-low: '#151c28'
  surface-container: '#19202c'
  surface-container-high: '#232a37'
  surface-container-highest: '#2e3542'
  on-surface: '#dce2f4'
  on-surface-variant: '#bfc7d2'
  inverse-surface: '#dce2f4'
  inverse-on-surface: '#2a313e'
  outline: '#89919c'
  outline-variant: '#404751'
  surface-tint: '#97cbff'
  primary: '#97cbff'
  on-primary: '#003354'
  primary-container: '#4dabf7'
  on-primary-container: '#003d64'
  inverse-primary: '#00639c'
  secondary: '#b9c8de'
  on-secondary: '#233143'
  secondary-container: '#39485a'
  on-secondary-container: '#a7b6cc'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#e59300'
  on-tertiary-container: '#553300'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#cee5ff'
  primary-fixed-dim: '#97cbff'
  on-primary-fixed: '#001d33'
  on-primary-fixed-variant: '#004a77'
  secondary-fixed: '#d4e4fa'
  secondary-fixed-dim: '#b9c8de'
  on-secondary-fixed: '#0d1c2d'
  on-secondary-fixed-variant: '#39485a'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#0d1320'
  on-background: '#dce2f4'
  surface-variant: '#2e3542'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  container-max: 1280px
  gutter: 24px
---

## Brand & Style
The design system focuses on "Compliance-First Financial Guidance," emphasizing stability, precision, and unwavering reliability. The transition to a dark interface shifts the brand from a standard corporate feel to a high-end, "Terminal" aesthetic that signals technical sophistication and 24/7 financial monitoring.

The style is **Corporate Modern with subtle Glassmorphism**. It utilizes deep charcoal surfaces and crisp, high-contrast typography to ensure information density remains legible without causing eye strain. The target audience includes compliance officers, financial analysts, and risk managers who require a focused, low-glare environment for long-duration analysis. The emotional response is one of "Quiet Authority"—a calm, controlled space where data clarity is the highest priority.

## Colors
The palette is built upon a "Deep Navy" foundation to maintain the psychology of trust associated with financial institutions. 

- **Primary (#4dabf7):** A bright, luminous blue optimized for dark mode. It serves as the primary action color and focal point for data highlights.
- **Secondary (#94a3b8):** A muted slate blue-grey used for secondary text and decorative elements to reduce visual noise.
- **Neutral (#0b121e):** The core background color, providing a solid, light-absorbent base.
- **Disclaimer Gold (#453008):** For the sticky banner, we use a deep, desaturated gold background with high-contrast text (#fbbf24) to signal caution without breaking the dark-theme immersion.

All text pairings are strictly audited to exceed WCAG AA contrast ratios (4.5:1 for normal text).

## Typography
This design system uses **Inter** exclusively to lean into its systematic, utilitarian nature. In dark mode, font-weights are slightly increased or adjusted to prevent "thinned" rendering on high-resolution screens.

- **Headlines:** Use a tighter letter-spacing and bold weights to ground the page hierarchy.
- **Body Text:** Uses a standard weight (400) but relies on `surface-1` or `surface-2` text colors to create a clear reading hierarchy.
- **Labels:** Uppercase and tracked out for immediate identification of data categories and status tags.

## Layout & Spacing
The layout follows a **Fixed Grid** approach for desktop dashboards to ensure data tables and charts remain in predictable locations. On mobile, it transitions to a fluid single-column layout.

- **Desktop:** 12-column grid, 1280px max-width, 24px gutters.
- **Tablet:** 8-column grid, 16px gutters, 24px side margins.
- **Mobile:** 4-column fluid grid, 16px side margins.

Spacing follows a strict 4px/8px baseline rhythm. This ensures that even in complex financial views, the "air" between elements feels intentional and structured.

## Elevation & Depth
In this dark mode environment, depth is communicated through **Tonal Layering** and **Subtle Outlines** rather than traditional shadows, which can appear muddy on dark backgrounds.

- **Level 0 (Background):** #0b121e. Used for the main canvas.
- **Level 1 (Cards/Sidebar):** #161f2e. Elevated with a 1px solid border of `rgba(255, 255, 255, 0.08)`.
- **Level 2 (Modals/Popovers):** #1e293b. Elevated with a 1px solid border of `rgba(255, 255, 255, 0.15)` and a very soft, large-radius black shadow (0px 8px 24px rgba(0,0,0,0.4)).

Interaction states (hover/active) are indicated by increasing the border opacity or slightly lightening the surface fill, creating a "lit from within" effect.

## Shapes
The shape language is **Soft (0.25rem)**. This provides a professional, "to-the-point" aesthetic that feels modern but retains the structural rigidity required for financial applications. 

- **Small Components (Buttons, Inputs):** 4px (0.25rem).
- **Medium Components (Cards, Modals):** 8px (0.5rem).
- **Large Components (Containers):** 12px (0.75rem).

## Components

- **Buttons:** 
  - *Primary:* Filled with `#4dabf7`, black text for maximum legibility.
  - *Secondary:* Ghost variant with a 1px border of `#4dabf7` and blue text.
- **Input Fields:** 
  - Background: `#161f2e` (Surface-1).
  - Border: 1px solid `rgba(255, 255, 255, 0.1)`. 
  - Focus State: Border becomes `#4dabf7` with a subtle outer glow.
- **Chat Bubbles:**
  - *System/AI:* Surface-2 (#1e293b) with a left-accent border in Primary Blue.
  - *User:* Surface-1 (#161f2e) with a subtle white-translucent border.
- **Cards:**
  - No shadows. Use Surface-1 fill and a 1px `border-subtle`. Titles should use `headline-md`.
- **Status Chips:**
  - Use low-opacity fills (15%) of the status color (e.g., green for compliant, red for risk) with high-saturation text for clarity.
- **Sticky Disclaimer:**
  - Positioned at the top or bottom of the viewport. Use `banner-gold` background with `banner-gold-text`. Ensure a 1px border separates it from the main content.