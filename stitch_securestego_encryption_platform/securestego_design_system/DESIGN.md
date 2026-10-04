---
name: SecureStego Design System
colors:
  surface: '#0e141c'
  surface-dim: '#0e141c'
  surface-bright: '#343a42'
  surface-container-lowest: '#090f16'
  surface-container-low: '#161c24'
  surface-container: '#1a2028'
  surface-container-high: '#242a33'
  surface-container-highest: '#2f353e'
  on-surface: '#dde3ee'
  on-surface-variant: '#bbcac6'
  inverse-surface: '#dde3ee'
  inverse-on-surface: '#2b3139'
  outline: '#859490'
  outline-variant: '#3c4947'
  surface-tint: '#4fdbc8'
  primary: '#4fdbc8'
  on-primary: '#003731'
  primary-container: '#14b8a6'
  on-primary-container: '#00423b'
  inverse-primary: '#006b5f'
  secondary: '#adc6ff'
  on-secondary: '#002e6a'
  secondary-container: '#0566d9'
  on-secondary-container: '#e6ecff'
  tertiary: '#ffb59e'
  on-tertiary: '#5e1800'
  tertiary-container: '#f38764'
  on-tertiary-container: '#6c2106'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#71f8e4'
  primary-fixed-dim: '#4fdbc8'
  on-primary-fixed: '#00201c'
  on-primary-fixed-variant: '#005048'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#ffdbd0'
  tertiary-fixed-dim: '#ffb59e'
  on-tertiary-fixed: '#3a0b00'
  on-tertiary-fixed-variant: '#7c2d11'
  background: '#0e141c'
  on-background: '#dde3ee'
  surface-variant: '#2f353e'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-sm:
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
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  headline-md-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  gutter: 24px
  container-max: 1200px
---

## Brand & Style
The design system is engineered for a high-security environment where precision and trust are paramount. It adopts a **Corporate / Modern** aesthetic with a lean toward **Technical Minimalism**. The personality is authoritative yet accessible, evoking the feeling of a sophisticated cryptography suite or a high-end fintech platform. 

The interface avoids "alarmist" security tropes (bright reds, glitch effects) in favor of a stable, calm atmosphere. It uses generous whitespace to reduce cognitive load during complex tasks like data embedding and extraction. Visual reliability is established through a strict geometric grid, subtle depth, and a focused technical palette.

## Colors
This design system utilizes a "Deep Tech" dark mode palette. The background is a dense navy-charcoal (#0A0E14) to provide maximum contrast for technical data.

- **Primary (Teal):** Used for the most critical actions, representing "active security" and precision.
- **Secondary (Electric Blue):** Used for navigation, links, and secondary interactive elements.
- **Neutral Grays:** Used for structural borders and hierarchy in typography. 
- **Functional States:** Success and Error states are handled with desaturated, "neutral-warning" tones to maintain a professional composure, avoiding high-vibrancy reds or greens that might feel unprofessional or panicked.

## Typography
The system relies on **Inter** for its exceptional legibility in digital interfaces and its neutral, professional character. For technical metadata, hex codes, and file paths, **JetBrains Mono** is used to provide a "developer-tool" feel that reinforces the application's technical nature.

Hierarchy is strictly enforced through weight and scale. Headlines use tighter letter spacing for a more "locked-in" appearance, while body text remains spacious for readability. Mobile scaling reduces the primary display sizes to ensure large headers do not break the layout on smaller screens.

## Layout & Spacing
The layout follows a **Fixed-Fluid Hybrid** model. Content is centered within a 1200px container on desktop, utilizing a 12-column grid.

- **Desktop:** 12 columns, 24px gutters, 48px+ side margins.
- **Tablet:** 8 columns, 16px gutters, 24px side margins.
- **Mobile:** 4 columns, 16px gutters, 16px side margins.

The spacing rhythm is strictly based on 8px increments. Drag-and-drop zones and image preview areas should utilize the `lg` (48px) padding to create a "gallery" feel, emphasizing the visual nature of the steganography process.

## Elevation & Depth
Depth is created using a **Tonal Layering** approach combined with subtle ambient shadows. 

1. **Base (Level 0):** #0A0E14 (Main background).
2. **Surface (Level 1):** #121820 (Cards, sidebars). Features a 1px solid border (#2D3748) for definition.
3. **Elevated (Level 2):** Used for modals and dropdowns. These use a slightly lighter background and a soft, desaturated shadow: `0px 10px 30px rgba(0, 0, 0, 0.5)`.

Instead of heavy dividers, the system uses variations in background color and generous whitespace to separate logical sections.

## Shapes
The design system uses a consistent **Rounded** geometry (8px to 12px) to soften the technical nature of the app and make it feel more "modern-web" than "legacy-software."

- **Standard Components:** 8px radius (buttons, inputs, small cards).
- **Large Containers:** 16px radius (main upload zones, large image previews).
- **Pill Elements:** 999px (tab switchers, status tags).

## Components

### Buttons & Inputs
- **Primary Button:** Solid Teal (#14B8A6) with white or near-white text. 8px border radius. No gradients.
- **Secondary Button:** Ghost style with a thin border (#2D3748) and a subtle hover state that fills the background with a 10% opacity blue.
- **Inputs:** Darker background than the card surface. Focused state uses a 1px Electric Blue border and a subtle outer glow.

### Drag-and-Drop Zones
- **Style:** Dashed border (2px width, 4px dash) in gray-600.
- **Interaction:** On drag-over, the border transitions to solid Teal with a faint Teal tinted background-fill.

### Tab Switchers
- **Pill Style:** A container with a dark background (#0A0E14) where the active tab is an elevated card-like pill. This provides a tactile feel to the navigation.

### Success & Error States
- **Toasts:** Use low-contrast backgrounds. Success uses a deep forest green background with light teal text. Errors use a deep burgundy background with soft pink/red text.
- **Icons:** Use a custom-picked set of minimal, 2px stroke icons (Lock, Shield, Key) for a consistent technical vibe.

### Loading States
- **Spinners:** Use a discrete, thin-ring teal spinner. For larger file processing, use a linear progress bar to reflect the "technical calculation" aspect.