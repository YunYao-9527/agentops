# Frontend Dependencies

Pinned, self-hosted browser assets avoid depending on third-party CDN availability:

- HTMX 1.9.10, Zero-Clause BSD; see `htmx-LICENSE`.
- Alpine.js 3.13.3, MIT; see `alpine-LICENSE.md`.
- Tailwind CSS 3.4.17, MIT; see `tailwind-LICENSE`.

Regenerate `tailwind.css` after changing template utility classes:

```sh
npx --yes tailwindcss@3.4.17 --content './src/web/templates/**/*.html' --input src/web/static/vendor/tailwind.source.css --output src/web/static/vendor/tailwind.css --minify
```

The distributed Alpine and HTMX files are unmodified npm package assets.
