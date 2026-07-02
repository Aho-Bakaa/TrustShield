import "./globals.css";

export const metadata = {
  title: "TrustShield — Securities-Market Trust Layer",
  description:
    "Multimodal detection of AI-generated phishing, synthetic voice, and social manipulation, with authenticity verification for legitimate securities-market communications.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="text-slate-100 antialiased">{children}</body>
    </html>
  );
}
