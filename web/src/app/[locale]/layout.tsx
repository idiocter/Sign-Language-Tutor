import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing, type Locale } from "@/i18n/routing";
import Nav from "@/components/Nav";
import "../globals.css";

export const metadata: Metadata = {
  title: "SignBridge",
  description: "Bilingual Nepali Sign Language tutor and interpreter",
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as Locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          <div className="mx-auto flex min-h-screen max-w-5xl flex-col">
            <Nav />
            <main className="flex-1 px-6 py-8">{children}</main>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
