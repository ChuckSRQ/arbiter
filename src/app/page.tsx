export default function Home() {
  return (
    <main className="min-h-[100dvh] bg-[#101234] px-6 py-10 text-[#F7F1E6] md:px-12">
      <section className="mx-auto flex max-w-6xl flex-col gap-10">
        <nav className="flex items-center justify-between border-b border-[#3B82C4]/25 pb-5">
          <div>
            <p className="text-sm tracking-[0.18em] text-[#8FC5F4] uppercase">Kalshi intelligence</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em] text-white md:text-6xl">Arbiter</h1>
          </div>
          <div className="rounded-full border border-[#3B82C4]/40 px-4 py-2 text-sm text-[#CFE7FF]">
            Session 1 pending
          </div>
        </nav>

        <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
          <section className="rounded-[28px] border border-[#3B82C4]/25 bg-[#1B1B4A] p-8 shadow-2xl shadow-[#070817]/40">
            <p className="text-sm tracking-[0.16em] text-[#8FC5F4] uppercase">Product thesis</p>
            <h2 className="mt-4 max-w-3xl text-3xl font-medium tracking-[-0.03em] text-white md:text-5xl">
              Judge market prices against evidence before risking capital.
            </h2>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-[#E8DECB]">
              Arbiter will scan Kalshi markets expiring in the next month, review the portfolio, and publish a daily edge report focused on the few trades worth attention — including no-trade days.
            </p>
          </section>

          <aside className="rounded-[28px] border border-[#3B82C4]/25 bg-[#151743] p-6">
            <p className="text-sm tracking-[0.16em] text-[#8FC5F4] uppercase">V1 constraints</p>
            <ul className="mt-5 space-y-4 text-[#F7F1E6]">
              <li>• Kalshi-first, not Polymarket-first</li>
              <li>• Polling-first for politics</li>
              <li>• F1 uses pace data</li>
              <li>• No automatic trading</li>
              <li>• Top 3-5 opportunities only</li>
            </ul>
          </aside>
        </div>

        <section className="grid gap-4 md:grid-cols-4">
          {[
            ["Today", "Daily recommendation report"],
            ["Opportunities", "Ranked edge candidates"],
            ["Portfolio", "Hold, reduce, exit review"],
            ["Evidence", "Polling, pace, official data"],
          ].map(([title, body]) => (
            <div key={title} className="rounded-3xl border border-[#3B82C4]/20 bg-[#171943] p-5">
              <h3 className="text-lg font-semibold text-white">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-[#E8DECB]">{body}</p>
            </div>
          ))}
        </section>
      </section>
    </main>
  );
}
