import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Epis-KG — Epistemic Erosion Knowledge Graph",
  description:
    "Visualise and mathematically score epistemic decay across digital communication networks.",
};

// Set the theme before first paint to avoid a flash of the wrong palette.
const themeScript = `
(function () {
  try {
    var t = localStorage.getItem('epis-theme');
    if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    if (t === 'dark') document.documentElement.classList.add('dark');
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
