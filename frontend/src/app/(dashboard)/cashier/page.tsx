"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  ShoppingCart, Users, Clock, CheckCircle2, UserPlus,
  Search, Loader2, X, RefreshCw, Receipt, Banknote,
  CreditCard, Smartphone, Building2, UserCheck, Info,
} from "lucide-react";
import Loading from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import Modal from "@/components/ui/Modal";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import ForbiddenPage from "@/components/ui/ForbiddenPage";
import { useToast } from "@/components/ui/ToastProvider";
import { usePermission } from "@/hooks/usePermission";
import { formatDateTime } from "@/utils/formatDate";
import { getCustomers } from "@/services/customer.service";
import type { Customer } from "@/types/customer.type";
import {
  getInStoreVisitors,
  linkProfileToCustomer,
  createOrder,
  PAYMENT_METHOD_LABELS,
  type InStoreVisitor,
  type CreateOrderPayload,
} from "@/services/cashier.service";

const POLL_INTERVAL = 5000; // 5 giây

// ─── Visitor Card ─────────────────────────────────────────────────────────────
function VisitorCard({
  visitor,
  selected,
  onClick,
}: {
  visitor: InStoreVisitor;
  selected: boolean;
  onClick: () => void;
}) {
  const entryDate = new Date(visitor.entry_time);
  const diffMin = Math.round((Date.now() - entryDate.getTime()) / 60000);
  const timeLabel = diffMin < 1 ? "Vừa vào" : `${diffMin} phút trước`;

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 rounded-2xl border p-3.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? "border-amber-400 ring-2 ring-amber-400/20 dark:border-amber-500"
          : ""
      }`}
      style={{
        background: "var(--bg-surface)",
        borderColor: selected ? undefined : "var(--border)",
      }}
    >
      {/* Face */}
      <div className="relative h-12 w-12 shrink-0">
        <img
          src={visitor.face_image_url ?? "https://placehold.co/48x48/e2e8f0/64748b?text=?"}
          alt="face"
          className="h-12 w-12 rounded-xl object-cover ring-2 ring-slate-200 dark:ring-slate-700"
        />
        {visitor.person_type === "identified" && (
          <span className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-white dark:ring-slate-800">
            <CheckCircle2 className="h-3 w-3 text-white" />
          </span>
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          {visitor.customer?.full_name ?? visitor.anonymous_code}
        </p>
        <p className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
          {visitor.anonymous_code}
          {visitor.customer && (
            <span className="ml-1 not-italic text-emerald-600 dark:text-emerald-400">
              · {visitor.customer.customer_code}
            </span>
          )}
        </p>
        <div className="mt-1 flex items-center gap-1">
          <Clock className="h-3 w-3 shrink-0" style={{ color: "var(--text-muted)" }} />
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>{timeLabel}</span>
        </div>
      </div>

      {/* Badge */}
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
        visitor.person_type === "identified"
          ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"
          : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
      }`}>
        {visitor.person_type === "identified" ? "Đã nhận diện" : "Ẩn danh"}
      </span>
    </button>
  );
}

// ─── Identify Panel ───────────────────────────────────────────────────────────
function IdentifyPanel({
  visitor,
  onSuccess,
  onCancel,
}: {
  visitor: InStoreVisitor;
  onSuccess: (updated: InStoreVisitor) => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [tab, setTab] = useState<"existing" | "new">("existing");
  const [search, setSearch] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [linking, setLinking] = useState(false);

  // New customer form
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newGender, setNewGender] = useState<"male" | "female" | "other">("male");
  const [creating, setCreating] = useState(false);

  // Search existing customers
  useEffect(() => {
    if (!search.trim()) { setCustomers([]); return; }
    setSearchLoading(true);
    getCustomers({ search, limit: 10, page: 1 })
      .then((res) => setCustomers(res.data))
      .catch(() => {})
      .finally(() => setSearchLoading(false));
  }, [search]);

  async function handleLink() {
    if (!selectedCustomer) return;
    setLinking(true);
    try {
      await linkProfileToCustomer(
        { person_profile_id: visitor.profile_id, customer_id: selectedCustomer.id },
        {
          id: selectedCustomer.id,
          customer_code: selectedCustomer.customer_code ?? "",
          full_name: selectedCustomer.full_name,
          phone: selectedCustomer.phone ?? null,
        },
      );
      toast.success(`Đã liên kết với ${selectedCustomer.full_name}`);
      onSuccess({
        ...visitor,
        person_type: "identified",
        customer: {
          id: selectedCustomer.id,
          customer_code: selectedCustomer.customer_code ?? "",
          full_name: selectedCustomer.full_name,
          phone: selectedCustomer.phone ?? null,
        },
      });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Liên kết thất bại");
    } finally {
      setLinking(false);
    }
  }

  async function handleCreateNew() {
    if (!newName.trim()) { toast.error("Vui lòng nhập họ tên"); return; }
    setCreating(true);
    try {
      // TODO: khi BE xong CASH-06, gọi API tạo customer kèm person_profile_id
      // Hiện tại mock thành công
      await new Promise((r) => setTimeout(r, 600));
      const mockCustomer = {
        id: Date.now(),
        customer_code: `CUS${String(Date.now()).slice(-6)}`,
        full_name: newName.trim(),
        phone: newPhone.trim() || null,
      };
      toast.success(`Đã tạo khách hàng "${newName}" và liên kết`);
      onSuccess({ ...visitor, person_type: "identified", customer: mockCustomer });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Tạo khách hàng thất bại");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Profile info */}
      <div className="flex items-center gap-3 rounded-xl p-3" style={{ background: "var(--bg-surface-2)" }}>
        <img
          src={visitor.face_image_url ?? "https://placehold.co/40x40/e2e8f0/64748b?text=?"}
          alt="face"
          className="h-10 w-10 rounded-lg object-cover"
        />
        <div>
          <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>{visitor.anonymous_code}</p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Vào lúc {formatDateTime(visitor.entry_time)}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl p-1" style={{ background: "var(--bg-surface-2)" }}>
        {([
          { key: "existing", label: "Khách có sẵn", icon: <Search className="h-3.5 w-3.5" /> },
          { key: "new",      label: "Khách mới",    icon: <UserPlus className="h-3.5 w-3.5" /> },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-all ${
              tab === t.key
                ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
            }`}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* Tab: Existing */}
      {tab === "existing" && (
        <div className="space-y-3">
          <Input
            placeholder="Tìm theo tên, SĐT, mã KH..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            leftIcon={<Search className="h-4 w-4" />}
          />
          {searchLoading && <Loading text="Đang tìm..." />}
          {!searchLoading && customers.length > 0 && (
            <div className="max-h-52 space-y-1 overflow-y-auto">
              {customers.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCustomer(c)}
                  className={`w-full flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${
                    selectedCustomer?.id === c.id
                      ? "border-amber-400 bg-amber-50 dark:bg-amber-900/20"
                      : "hover:bg-slate-50 dark:hover:bg-slate-800"
                  }`}
                  style={{ borderColor: selectedCustomer?.id === c.id ? undefined : "var(--border)" }}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-700 text-sm font-bold text-slate-600 dark:text-slate-300">
                    {(c.full_name || "K").charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{c.full_name}</p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>{c.customer_code} · {c.phone ?? "—"}</p>
                  </div>
                  {selectedCustomer?.id === c.id && <CheckCircle2 className="h-4 w-4 text-amber-500 shrink-0" />}
                </button>
              ))}
            </div>
          )}
          {!searchLoading && search && customers.length === 0 && (
            <p className="py-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>Không tìm thấy khách hàng</p>
          )}
          {!search && (
            <p className="py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>Nhập tên, SĐT hoặc mã để tìm kiếm</p>
          )}
          <Button
            className="w-full"
            disabled={!selectedCustomer || linking}
            loading={linking}
            onClick={handleLink}
          >
            <UserCheck className="mr-1.5 h-4 w-4" />
            Xác nhận liên kết
          </Button>
        </div>
      )}

      {/* Tab: New */}
      {tab === "new" && (
        <div className="space-y-3">
          <div>
            <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
              Họ và tên <span className="text-red-500">*</span>
            </label>
            <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Nhập họ và tên" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Số điện thoại</label>
            <Input value={newPhone} onChange={(e) => setNewPhone(e.target.value)} placeholder="0901234567" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Giới tính</label>
            <Select
              value={newGender}
              options={[
                { value: "male", label: "Nam" },
                { value: "female", label: "Nữ" },
                { value: "other", label: "Khác" },
              ]}
              onChange={(v) => setNewGender(v as "male" | "female" | "other")}
              ariaLabel="Giới tính"
            />
          </div>
          <Button className="w-full" loading={creating} onClick={handleCreateNew}>
            <UserPlus className="mr-1.5 h-4 w-4" />
            Tạo khách hàng & Liên kết
          </Button>
        </div>
      )}
    </div>
  );
}

// ─── Order Form ───────────────────────────────────────────────────────────────
function OrderForm({
  visitor,
  onSuccess,
  onCancel,
}: {
  visitor: InStoreVisitor;
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "card" | "transfer" | "e_wallet">("cash");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    const numAmount = parseFloat(amount.replace(/,/g, ""));
    if (!amount || isNaN(numAmount) || numAmount < 0) {
      toast.error("Vui lòng nhập tổng tiền hợp lệ (>= 0)");
      return;
    }

    setSubmitting(true);
    try {
      const payload: CreateOrderPayload = {
        person_profile_id: visitor.profile_id,
        customer_id: visitor.customer?.id ?? null,
        total_amount: numAmount,
        item_summary: description.trim() || undefined,
        payment_method: paymentMethod,
      };
      const result = await createOrder(payload);
      toast.success(`Đã tạo đơn hàng ${result.order_code} — ${numAmount.toLocaleString()}đ`);
      onSuccess();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Tạo đơn thất bại");
    } finally {
      setSubmitting(false);
    }
  }

  const paymentIcons: Record<string, React.ReactNode> = {
    cash:      <Banknote className="h-4 w-4" />,
    card:      <CreditCard className="h-4 w-4" />,
    transfer:  <Building2 className="h-4 w-4" />,
    e_wallet:  <Smartphone className="h-4 w-4" />,
  };

  return (
    <div className="space-y-4">
      {/* Customer summary */}
      <div className="flex items-center gap-3 rounded-xl p-3" style={{ background: "var(--bg-surface-2)" }}>
        <img
          src={visitor.face_image_url ?? "https://placehold.co/40x40/e2e8f0/64748b?text=?"}
          alt="face"
          className="h-10 w-10 rounded-lg object-cover"
        />
        <div>
          <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
            {visitor.customer?.full_name ?? visitor.anonymous_code}
          </p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {visitor.customer ? `${visitor.customer.customer_code} · ${visitor.customer.phone ?? "—"}` : "Khách ẩn danh"}
          </p>
        </div>
      </div>

      {/* Amount */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          Tổng tiền <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <Input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0"
            type="number"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold" style={{ color: "var(--text-muted)" }}>
            VND
          </span>
        </div>
        {amount && !isNaN(parseFloat(amount)) && (
          <p className="mt-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            = {parseFloat(amount).toLocaleString()}đ
          </p>
        )}
      </div>

      {/* Description */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          Mô tả hàng mua
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="VD: Cà phê sữa đá + bánh mì..."
          rows={2}
          className="w-full resize-none rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-amber-500/30"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-surface-2)",
            color: "var(--text-primary)",
          }}
        />
      </div>

      {/* Payment method */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          Phương thức thanh toán
        </label>
        <div className="grid grid-cols-2 gap-2">
          {(["cash", "card", "transfer", "e_wallet"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setPaymentMethod(m)}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-semibold transition ${
                paymentMethod === m
                  ? "border-amber-400 bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
                  : "hover:bg-slate-50 dark:hover:bg-slate-800"
              }`}
              style={{ borderColor: paymentMethod === m ? undefined : "var(--border)", color: paymentMethod === m ? undefined : "var(--text-secondary)" }}
            >
              {paymentIcons[m]}
              {PAYMENT_METHOD_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <Button variant="secondary" onClick={onCancel} disabled={submitting} className="flex-1">
          Hủy
        </Button>
        <Button onClick={handleSubmit} loading={submitting} className="flex-1">
          <Receipt className="mr-1.5 h-4 w-4" />
          Tạo đơn hàng
        </Button>
      </div>
    </div>
  );
}

// ─── Right panel ──────────────────────────────────────────────────────────────
type PanelMode = "idle" | "identify" | "order";

function RightPanel({
  selected,
  onIdentifySuccess,
  onOrderSuccess,
}: {
  selected: InStoreVisitor | null;
  onIdentifySuccess: (updated: InStoreVisitor) => void;
  onOrderSuccess: () => void;
}) {
  const [mode, setMode] = useState<PanelMode>("idle");

  useEffect(() => { setMode("idle"); }, [selected?.session_id]);

  if (!selected) {
    return (
      <div
        className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-900/20">
          <ShoppingCart className="h-7 w-7 text-amber-500" />
        </div>
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Chọn khách hàng</p>
        <p className="max-w-[200px] text-center text-xs" style={{ color: "var(--text-muted)" }}>
          Click vào một người trong danh sách để thao tác
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-2xl"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      {/* Header */}
      <div className="shrink-0 px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
        <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          {selected.customer?.full_name ?? selected.anonymous_code}
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Vào lúc {formatDateTime(selected.entry_time)}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {mode === "idle" && (
          <div className="space-y-3">
            {/* Action buttons */}
            {selected.person_type === "anonymous" && (
              <button
                onClick={() => setMode("identify")}
                className="flex w-full items-center gap-3 rounded-2xl border p-4 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800"
                style={{ borderColor: "var(--border)" }}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 dark:bg-emerald-500/10">
                  <UserCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Định danh khách</p>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>Liên kết với khách có sẵn hoặc tạo mới</p>
                </div>
              </button>
            )}

            {selected.person_type === "identified" && (
              <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2.5 dark:bg-emerald-500/10">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                <div>
                  <p className="text-xs font-bold text-emerald-700 dark:text-emerald-400">Đã nhận diện</p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-500">
                    {selected.customer?.full_name} · {selected.customer?.phone ?? "—"}
                  </p>
                </div>
              </div>
            )}

            <button
              onClick={() => setMode("order")}
              className="flex w-full items-center gap-3 rounded-2xl border p-4 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-500/10">
                <Receipt className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Ghi nhận đơn hàng</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Nhập tổng tiền và tạo đơn</p>
              </div>
            </button>

            <div
              className="flex items-start gap-2 rounded-xl px-3 py-2.5 text-xs"
              style={{ background: "var(--bg-surface-2)", color: "var(--text-muted)" }}
            >
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>Có thể tạo đơn cho cả khách ẩn danh — đơn sẽ lưu theo mã AI camera.</span>
            </div>
          </div>
        )}

        {mode === "identify" && (
          <IdentifyPanel
            visitor={selected}
            onSuccess={(updated) => { onIdentifySuccess(updated); setMode("idle"); }}
            onCancel={() => setMode("idle")}
          />
        )}

        {mode === "order" && (
          <OrderForm
            visitor={selected}
            onSuccess={() => { onOrderSuccess(); setMode("idle"); }}
            onCancel={() => setMode("idle")}
          />
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function CashierPage() {
  const { hasPermission } = usePermission();
  const toast = useToast();

  const [visitors, setVisitors] = useState<InStoreVisitor[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selected = visitors.find((v) => v.session_id === selectedId) ?? null;

  const fetchVisitors = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const { data, total } = await getInStoreVisitors();
      setVisitors(data);
      setTotal(total);
    } catch (e) {
      if (!silent) toast.error("Không tải được danh sách khách");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Initial load + polling 5s
  useEffect(() => {
    fetchVisitors();
    pollRef.current = setInterval(() => fetchVisitors(true), POLL_INTERVAL);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchVisitors]);

  if (!hasPermission("cashier.view")) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền truy cập trang Thu ngân. Vui lòng liên hệ quản trị viên."
        backHref="/dashboard"
        backLabel="Về Dashboard"
      />
    );
  }

  function handleIdentifySuccess(updated: InStoreVisitor) {
    setVisitors((prev) => prev.map((v) => v.session_id === updated.session_id ? updated : v));
  }

  function handleOrderSuccess() {
    setSelectedId(null);
    fetchVisitors(true);
  }

  const identified = visitors.filter((v) => v.person_type === "identified").length;
  const anonymous = visitors.filter((v) => v.person_type === "anonymous").length;

  return (
    <div className="flex h-[calc(100vh-120px)] flex-col gap-5">
      {/* Header */}
      <div className="flex shrink-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            <ShoppingCart className="h-3 w-3" />
            Thu ngân
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Quầy thu ngân
          </h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
            Danh sách khách đang trong cửa hàng · Polling mỗi 5 giây
          </p>
        </div>
        <button
          onClick={() => fetchVisitors()}
          className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition hover:bg-slate-50 dark:hover:bg-slate-800"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Làm mới
        </button>
      </div>

      {/* Stats */}
      <div className="grid shrink-0 grid-cols-3 gap-3">
        {[
          { label: "Đang trong cửa hàng", value: total,      color: "text-amber-600 dark:text-amber-400",   bg: "bg-amber-50 dark:bg-amber-500/10",   icon: <Users className="h-5 w-5" /> },
          { label: "Đã nhận diện",         value: identified, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10", icon: <UserCheck className="h-5 w-5" /> },
          { label: "Ẩn danh",              value: anonymous,  color: "text-slate-600 dark:text-slate-400",   bg: "bg-slate-100 dark:bg-slate-800",       icon: <Users className="h-5 w-5" /> },
        ].map((s) => (
          <div key={s.label} className="flex items-center gap-3 rounded-2xl p-4"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${s.bg} ${s.color}`}>
              {s.icon}
            </div>
            <div>
              <p className={`text-xl font-black ${s.color}`}>{s.value}</p>
              <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Main 2-col layout */}
      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[1fr_380px]">
        {/* Left: Visitor list */}
        <div
          className="flex flex-col overflow-hidden rounded-2xl"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <div className="shrink-0 flex items-center justify-between px-5 py-3.5"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Danh sách khách ({total})
            </h2>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>Live</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {loading ? (
              <Loading text="Đang tải danh sách khách..." />
            ) : visitors.length === 0 ? (
              <EmptyState
                title="Cửa hàng đang trống"
                description="Không có khách nào trong cửa hàng lúc này. Danh sách sẽ cập nhật tự động khi có khách mới."
                icon={<ShoppingCart className="mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />}
              />
            ) : (
              <div className="space-y-2">
                {visitors.map((v) => (
                  <VisitorCard
                    key={v.session_id}
                    visitor={v}
                    selected={selectedId === v.session_id}
                    onClick={() => setSelectedId(selectedId === v.session_id ? null : v.session_id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Action panel */}
        <RightPanel
          selected={selected}
          onIdentifySuccess={handleIdentifySuccess}
          onOrderSuccess={handleOrderSuccess}
        />
      </div>
    </div>
  );
}
