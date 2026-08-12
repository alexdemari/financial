import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Panel } from "./Panel";

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const statusIcon = { within: "✓", above: "↑", below: "↓" };

function MissingData({ account }) {
  if (account?.status !== "no_data") return null;
  return <div className="empty">Sem dados — <code>{account.hint}</code></div>;
}

function PositionTable({ rows, columns }) {
  if (!rows?.length) return <div className="empty">Nenhuma posição.</div>;
  return <div className="table-wrap"><table><thead><tr>
    {columns.map((column) => <th key={column.key}>{column.label}</th>)}
  </tr></thead><tbody>
    {rows.map((row, index) => <tr key={`${row.symbol || row.codigo || row.ativo || index}-${index}`}>
      {columns.map((column) => <td key={column.key}>{column.format ? column.format(row[column.key]) : row[column.key] ?? "—"}</td>)}
    </tr>)}
  </tbody></table></div>;
}

function AccountSection({ title, account, columns }) {
  return <details className="account-details">
    <summary>{title} <span>{money.format(account?.total_brl || account?.nlv_brl || 0)}</span></summary>
    <MissingData account={account} />
    {account?.status !== "no_data" && <PositionTable rows={account?.positions} columns={columns} />}
  </details>;
}

export default function PatrimonioView({ data }) {
  if (!data) return <div className="empty">Carregando patrimônio…</div>;
  const allocation = Object.entries(data.allocation || {}).map(([key, value]) => ({ key, ...value }));
  const cashAccounts = data.cash_accounts || [];
  const cashTotalBrl = data.cash_total_brl || 0;
  const cashSummary = data.cash_summary || {};
  const crypto = data.crypto || { positions: [], total_brl: 0, stale: true };
  const chartData = allocation.filter((item) => item.value_brl > 0);
  const cashLatestAsOf = cashAccounts.reduce((latest, account) => {
    if (!account.as_of) return latest;
    if (!latest || account.as_of > latest) return account.as_of;
    return latest;
  }, "");
  const ibkrColumns = [
    { key: "symbol", label: "Ativo" },
    { key: "asset_type", label: "Tipo" },
    { key: "quantity", label: "Qtd." },
    { key: "market_value", label: "Valor USD", format: (value) => usd.format(value || 0) },
  ];
  const btgColumns = [
    { key: "codigo", label: "Ativo" },
    { key: "asset_type", label: "Tipo" },
    { key: "quantidade", label: "Qtd." },
    { key: "saldo_bruto", label: "Saldo bruto", format: (value) => money.format(value || 0) },
  ];
  const fixedIncomeColumns = [
    { key: "emissor", label: "Emissor" },
    { key: "ativo", label: "Ativo" },
    { key: "vencimento", label: "Vencimento" },
    { key: "saldo_liquido", label: "Saldo líquido", format: (value) => money.format(value || 0) },
  ];

  return <section>
    {!data.complete && <div className="data-warning">Total parcial: uma ou mais fontes estão ausentes ou sem PTAX.</div>}
    <div className="cards patrimonio-cards">
      <div className="card"><span>Patrimônio total</span><strong>{money.format(data.total_brl)}</strong>
        <small>PTAX {data.ptax ? data.ptax.toFixed(4) : "indisponível"} · {data.ptax_date || "—"}</small></div>
      <div className="card"><span>IBKR</span><strong>{usd.format(data.accounts.ibkr.nlv_usd)}</strong>
        <small>{money.format(data.accounts.ibkr.nlv_brl)}</small></div>
      <div className="card"><span>BTG-Opções</span><strong>{money.format(data.accounts.btg_opcoes.total_brl)}</strong>
        <small>{data.accounts.btg_opcoes.status === "no_data" ? data.accounts.btg_opcoes.hint : "BRL"}</small></div>
      <div className="card"><span>BTG-Geral</span><strong>{money.format(data.accounts.btg_geral.total_brl)}</strong>
        <small>{data.accounts.btg_geral.status === "no_data" ? data.accounts.btg_geral.hint : "BRL"}</small></div>
      <div className="card"><span>Caixa BRL</span><strong>{money.format(cashTotalBrl)}</strong>
        <small className={data.cash_stale ? "cash-warning" : ""}>
          {data.cash_stale
            ? "⚠ Caixa desatualizado — edite config/cash_accounts.yaml"
            : `Atualizado em ${cashLatestAsOf || "—"}`}
        </small></div>
      <div className="card"><span>Cripto</span><strong>{money.format(crypto.total_brl || 0)}</strong>
        <small className={crypto.stale ? "cash-warning" : ""}>
          {crypto.stale ? "⚠ Cripto desatualizado — rode: just crypto-snapshot" : `Atualizado em ${crypto.fetched_at || "—"}`}
        </small></div>
    </div>

    <div className="patrimonio-allocation">
      <Panel title="Alocação por classe">
        {chartData.length ? <div className="chart"><ResponsiveContainer>
          <PieChart><Pie data={chartData} dataKey="value_brl" nameKey="label" innerRadius="55%" outerRadius="80%">
            {chartData.map((item) => <Cell key={item.key} fill={item.color} />)}
          </Pie><Tooltip formatter={(value) => money.format(value)} /><Legend /></PieChart>
        </ResponsiveContainer></div> : <div className="empty">Sem dados para alocação.</div>}
      </Panel>
      <Panel title="Alocação vs metas">
        <div className="table-wrap"><table><thead><tr><th>Classe</th><th>Valor</th><th>Atual</th><th>Meta</th><th>Status</th></tr></thead>
          <tbody>{allocation.map((item) => <tr key={item.key}><td>{item.label}</td><td>{money.format(item.value_brl)}</td>
            <td>{item.pct_of_total.toFixed(1)}%</td><td>{item.target_min == null ? "sem target definido" : `${item.target_min}–${item.target_max}%`}</td>
            <td className={`target-${item.severity}`}>{item.status === "undefined" ? "—" : statusIcon[item.status]}</td></tr>)}
          <tr>
            <td>{cashSummary.label || "Caixa total"}</td>
            <td>{money.format(cashSummary.value_brl || 0)}</td>
            <td>{(cashSummary.pct_of_total || 0).toFixed(1)}%</td>
            <td>≤ {(cashSummary.target_max || 0)}%</td>
            <td className={`target-${cashSummary.severity || "outside"}`}>{statusIcon[cashSummary.status] || "⚠"}</td>
          </tr></tbody></table></div>
      </Panel>
    </div>

    <Panel title={`Valores em Trânsito · ${money.format(data.proventos_total_brl)}`}>
      <PositionTable rows={data.proventos_futuros} columns={[
        { key: "data_liquidacao", label: "Data liquidação" },
        { key: "descricao", label: "Descrição" },
        { key: "valor", label: "Valor", format: (value) => money.format(value || 0) },
        { key: "account", label: "Conta" },
      ]} />
    </Panel>

    <Panel title="Contas e posições">
      <AccountSection title="IBKR" account={data.accounts.ibkr} columns={ibkrColumns} />
      <AccountSection title="BTG-Opções" account={data.accounts.btg_opcoes} columns={btgColumns} />
      <AccountSection title="BTG-Geral" account={data.accounts.btg_geral} columns={btgColumns} />
      <details className="account-details"><summary>Renda Fixa <span>{money.format(data.renda_fixa.total_brl)}</span></summary>
        <MissingData account={data.renda_fixa} />
        {data.renda_fixa.status !== "no_data" && <PositionTable rows={data.renda_fixa.positions} columns={fixedIncomeColumns} />}
      </details>
      <details className="account-details"><summary>Cripto <span>{money.format(crypto.total_brl || 0)}</span></summary>
        <PositionTable rows={crypto.positions} columns={[
          { key: "asset", label: "Ativo" },
          { key: "quantity", label: "Quantidade" },
          { key: "value_usdt", label: "Valor USD", format: (value) => usd.format(value || 0) },
          { key: "value_brl", label: "Valor BRL", format: (value) => money.format(value || 0) },
        ]} />
      </details>
    </Panel>
  </section>;
}
