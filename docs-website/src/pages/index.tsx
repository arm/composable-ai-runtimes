import clsx from "clsx";
import Link from "@docusaurus/Link";
import Layout from "@theme/Layout";
import type { ReactElement } from "react";
import { homepageContent } from "../data/homepage";
import styles from "./index.module.css";

export default function Home(): ReactElement {
  const tutorialCards = homepageContent.bottomCards.filter((card) =>
    (card.to ?? "").startsWith("/tutorials/"),
  );
  const otherCards = homepageContent.bottomCards.filter(
    (card) => !(card.to ?? "").startsWith("/tutorials/"),
  );

  return (
    <Layout
      title={homepageContent.meta.title}
      description={homepageContent.meta.description}
    >
      <main className={styles.page}>
        <section className={styles.hero}>
          <div className={styles.heroContent}>
            <p className={styles.pill}>{homepageContent.badge}</p>
            <h1>{homepageContent.headline}</h1>
            <p className={styles.lead}>{homepageContent.lead}</p>
            <div className={styles.actions}>
              {homepageContent.heroLinks.map((link) => (
                <Link
                  key={link.label}
                  className={clsx(
                    `button button--${link.variant}`,
                    styles.button,
                  )}
                  to={link.to}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div className={styles.heroCard}>
            <div className={styles.cardHeader}>
              {homepageContent.installTitle}
            </div>
            <pre className={styles.codeBlock}>
              {homepageContent.installCommands.map((cmd) => (
                <div key={cmd}>
                  <code>{cmd}</code>
                </div>
              ))}
            </pre>
            <Link
              to={homepageContent.installCta.to}
              className={clsx(
                "button button--sm button--primary",
                styles.installCta,
              )}
            >
              {homepageContent.installCta.label}
            </Link>
          </div>
        </section>

        <section className={styles.bottom}>
          {otherCards.map((card) => (
            <div key={card.title} className={styles.bottomCard}>
              <div>
                <p className={styles.label}>{card.label}</p>
                <h4>{card.title}</h4>
                <p className={styles.small}>{card.description}</p>
              </div>
              {card.disabled ? (
                <span
                  className={clsx(
                    "button button--sm",
                    `button--${card.variant}`,
                    styles.buttonDisabled,
                  )}
                >
                  {card.cta}
                </span>
              ) : card.href ? (
                <a
                  href={card.href}
                  target="_blank"
                  rel="noreferrer"
                  className={clsx(
                    "button button--sm",
                    `button--${card.variant}`,
                  )}
                >
                  {card.cta}
                </a>
              ) : (
                <Link
                  to={
                    card.to ?? "/tutorials/getting-started/your-first-program"
                  }
                  className={clsx(
                    "button button--sm",
                    `button--${card.variant}`,
                  )}
                >
                  {card.cta}
                </Link>
              )}
            </div>
          ))}

          {tutorialCards.length > 0 && (
            <div className={styles.tutorialsBox}>
              <div className={styles.tutorialsHeader}>
                <p className={styles.label}>Tutorials</p>
                <h4>Get started with guided walkthroughs</h4>
              </div>
              <div className={styles.tutorialsGrid}>
                {tutorialCards.map((card) => (
                  <div key={card.title} className={styles.bottomCard}>
                    <div>
                      <p className={styles.label}>{card.label}</p>
                      <h4>{card.title}</h4>
                      <p className={styles.small}>{card.description}</p>
                    </div>
                    {card.href ? (
                      <a
                        href={card.href}
                        target="_blank"
                        rel="noreferrer"
                        className={clsx(
                          "button button--sm",
                          `button--${card.variant}`,
                        )}
                      >
                        {card.cta}
                      </a>
                    ) : (
                      <Link
                        to={
                          card.to ??
                          "/tutorials/getting-started/your-first-program"
                        }
                        className={clsx(
                          "button button--sm",
                          `button--${card.variant}`,
                        )}
                      >
                        {card.cta}
                      </Link>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className={styles.codeSection}>
          <div className={styles.codeIntro}>
            <p className={styles.codeEyebrow}>
              {homepageContent.codeExamples.eyebrow}
            </p>
            <h2>{homepageContent.codeExamples.title}</h2>
            <p>{homepageContent.codeExamples.subtitle}</p>
          </div>
          <div className={styles.codeGrid}>
            {homepageContent.codeExamples.items.map((example) => (
              <article key={example.title} className={styles.exampleCard}>
                <div className={styles.exampleHead}>
                  <span className={styles.exampleTag}>{example.label}</span>
                  <h3>{example.title}</h3>
                  <p>{example.description}</p>
                </div>
                <pre className={styles.exampleCode}>
                  <code>{example.code}</code>
                </pre>
                <p className={styles.exampleLang}>{example.language}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </Layout>
  );
}
