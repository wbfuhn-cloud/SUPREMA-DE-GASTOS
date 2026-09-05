const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Authorization, Content-Type",
  "Access-Control-Max-Age": "86400"
};

function json(data, status = 200, cacheSeconds = 0, etag = null) {
  const h = { ...JSON_HEADERS };
  if (cacheSeconds > 0) h["Cache-Control"] = `public, max-age=${cacheSeconds}`;
  if (etag) h["ETag"] = etag;
  return new Response(JSON.stringify(data), {
    status,
    headers: h,
  });
}

function authorized(request, env) {
  const expected = env.APP_ACCESS_TOKEN;
  if (!expected) return false;
  const actual = request.headers.get("authorization") || "";
  return actual === `Bearer ${expected}`;
}

function expensePayload(body) {
  const total = Number(body.total);
  if (!body.date || !Number.isFinite(total) || total < 0) {
    throw new Error("date y total son obligatorios y total debe ser valido");
  }
  return {
    date: String(body.date).slice(0, 10),
    merchant: String(body.merchant || "").trim().slice(0, 120),
    category: String(body.category || "OTRO").trim().toUpperCase().slice(0, 60),
    payment_method: String(body.payment_method || "EFECTIVO").trim().toUpperCase().slice(0, 60),
    details: String(body.details || "").trim().slice(0, 500),
    subcategory: String(body.subcategory || "").trim().slice(0, 100),
    project: String(body.project || "").trim().slice(0, 100),
    total,
    type: String(body.type || "Normal").slice(0, 30),
    status: String(body.status || "pending").slice(0, 30),
  };
}

async function api(request, env, url) {
  if (request.method === "OPTIONS") {
    return new Response(null, { headers: JSON_HEADERS });
  }

  if (!authorized(request, env)) return json({ error: "No autorizado" }, 401);

  try {
    if (request.method === "GET") {
      const { ts } = await env.DB.prepare("SELECT MAX(updated_at) AS ts FROM expenses").first();
      const etag = `"${btoa(ts || 'empty')}"`;

      if (request.headers.get("If-None-Match") === etag) {
        return new Response(null, { status: 304, headers: { ...JSON_HEADERS, "ETag": etag, "Cache-Control": "public, max-age=10" } });
      }

      const year = url.searchParams.get("year");
      const yearFilter = year ? ` WHERE date LIKE '${year}-%'` : '';

      if (url.pathname === "/api/expenses") {
        const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || 50, 1), 200);
        const offset = Math.max(Number(url.searchParams.get("offset")) || 0, 0);

        const countQ = year
          ? env.DB.prepare("SELECT COUNT(*) AS c FROM expenses WHERE date LIKE ?").bind(`${year}-%`)
          : env.DB.prepare("SELECT COUNT(*) AS c FROM expenses");
        const { c: totalCount } = await countQ.first();

        const query = year
          ? env.DB.prepare("SELECT * FROM expenses WHERE date LIKE ? ORDER BY date DESC, id DESC LIMIT ? OFFSET ?").bind(`${year}-%`, limit, offset)
          : env.DB.prepare("SELECT * FROM expenses ORDER BY date DESC, id DESC LIMIT ? OFFSET ?").bind(limit, offset);
        const { results } = await query.all();
        return json({ expenses: results, total_count: totalCount, has_more: offset + limit < totalCount }, 200, 10, etag);
      }

      if (url.pathname === "/api/summary") {
        const now = new Date().toISOString();
        const yearCondition = year ? ` AND date LIKE '${year}-%'` : '';
        const [general, monthly, debts, loans, unconfirmed] = await Promise.all([
          env.DB.prepare(`SELECT COUNT(*) AS count, COALESCE(SUM(total),0) AS total FROM expenses${yearFilter}`).first(),
          env.DB.prepare(`SELECT COALESCE(SUM(total),0) AS total FROM expenses WHERE date LIKE ?`).bind(`${now.slice(0,7)}-%`).first(),
          env.DB.prepare(`SELECT COALESCE(SUM(total),0) AS total FROM expenses WHERE type='Deuda' AND status='pending'${yearCondition}`).first(),
          env.DB.prepare(`SELECT COALESCE(SUM(total),0) AS total FROM expenses WHERE type='Prestamo' AND status='pending'${yearCondition}`).first(),
          env.DB.prepare(`SELECT COUNT(*) AS count FROM expenses WHERE status='unconfirmed'${yearCondition}`).first(),
        ]);
        return json({
          summary: {
            count: general.count, total: general.total,
            monthly_total: monthly.total, daily_avg: monthly.total / Math.max(new Date().getDate(), 1),
            debt_pending: debts.total, loan_pending: loans.total,
            unconfirmed_count: unconfirmed.count
          }
        }, 200, 10, etag);
      }

      if (url.pathname === "/api/categories") {
        const { results } = await env.DB.prepare(
          `SELECT category AS name, SUM(total) AS total FROM expenses${yearFilter} GROUP BY category ORDER BY total DESC LIMIT 8`
        ).all();
        return json({ categories: results }, 200, 10, etag);
      }

      if (url.pathname === "/api/pending") {
        const { results } = await env.DB.prepare(
          `SELECT id, date, merchant, total FROM expenses WHERE status='unconfirmed' ORDER BY date DESC LIMIT 10`
        ).all();
        return json({ pending: results }, 200, 10, etag);
      }
    }

    if (request.method === "POST" && url.pathname === "/api/expenses") {
      const body = expensePayload(await request.json());
      const result = await env.DB.prepare(`
        INSERT INTO expenses
          (date, merchant, category, payment_method, details, total, type, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).bind(
        body.date, body.merchant, body.category, body.payment_method,
        body.details, body.total, body.type, body.status
      ).run();
      return json({ id: result.meta.last_row_id }, 201);
    }

    const id = Number(url.pathname.split("/").pop());
    if (Number.isInteger(id) && id > 0 && ["PATCH", "POST"].includes(request.method)) {
      const body = expensePayload(await request.json());
      const result = await env.DB.prepare(`
        UPDATE expenses SET date=?, merchant=?, category=?, payment_method=?,
        details=?, subcategory=?, project=?, total=?, type=?, status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
      `).bind(
        body.date, body.merchant, body.category, body.payment_method,
        body.details, body.subcategory, body.project, body.total, body.type, body.status, id
      ).run();
      if (!result.meta.changes) return json({ error: "Gasto no encontrado" }, 404);
      return json({ ok: true });
    }

    if (Number.isInteger(id) && id > 0 && request.method === "DELETE") {
      const result = await env.DB.prepare("DELETE FROM expenses WHERE id = ?").bind(id).run();
      if (!result.meta.changes) return json({ error: "Gasto no encontrado" }, 404);
      return json({ ok: true });
    }

    return json({ error: "Ruta no encontrada" }, 404);
  } catch (error) {
    return json({ error: error.message || "Error interno" }, 400);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) return api(request, env, url);
    return env.ASSETS.fetch(request);
  },
};
