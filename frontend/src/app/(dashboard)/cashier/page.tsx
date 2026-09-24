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
import { createCustomer, getCustomers } from "@/services/customer.service";
import type { Customer } from "@/types/customer.type";
import {
  getInStoreVisitors,
  linkProfileToCustomer,
  createOrder,
  PAYMENT_METHOD_LABELS,
  type InStoreVisitor,
  type CreateOrderPayload,
} from "@/services/cashier.service";
import { isPointInPolygon, getFeetPosition, type Point } from "@/utils/geometry";

const POLL_INTERVAL = 5000; // 5 giây

// // Tọa độ Vùng Thu Ngân (Demo: góc dưới bên phải camera)
// // Bạn có thể chỉnh lại cho khớp với camera thực tế
// const CASHIER_ZONE: Point[] = [
//   { x: 0.6, y: 0.5 },
//   { x: 1.0, y: 0.5 },
//   { x: 1.0, y: 1.0 },
//   { x: 0.6, y: 1.0 }
// ];

// ─── Visitor Card ─────────────────────────────────────────────────────────────
function VisitorCard({
  visitor,
  selected,
  onClick,
}: {
  // Mở rộng kiểu dữ liệu để TypeScript chấp nhận các thuộc tính mới
  visitor: InStoreVisitor & { 
    isAtCashier?: boolean; 
    entry_video_time?: number; 
    latest_video_time?: number; 
  };
  selected: boolean;
  onClick: () => void;
}) {
  let timeLabel = "Vừa vào";
  if (visitor.entry_video_time !== undefined && visitor.latest_video_time !== undefined) {
    const diffSeconds = Math.max(0, visitor.latest_video_time - visitor.entry_video_time);
    if (diffSeconds < 60) {
      timeLabel = `Có mặt: ${Math.floor(diffSeconds)} giây`;
    } else {
      const m = Math.floor(diffSeconds / 60);
      const s = Math.floor(diffSeconds % 60);
      timeLabel = `Có mặt: ${m}p ${s}s`;
    }
  } else {
    const entryDate = new Date(visitor.entry_time);
    const diffMin = Math.round((Date.now() - entryDate.getTime()) / 60000);
    timeLabel = diffMin < 1 ? "Vừa vào" : `${diffMin} phút trước`;
  }

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 rounded-2xl border p-3.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? "border-amber-400 ring-2 ring-amber-400/20 dark:border-amber-500"
          : visitor.isAtCashier
            ? "border-red-500 ring-2 ring-red-500/20 animate-pulse bg-red-50/50 dark:bg-red-900/20"
            : ""
      }`}
      style={{
        background: visitor.isAtCashier ? undefined : "var(--bg-surface)",
        borderColor: selected || visitor.isAtCashier ? undefined : "var(--border)",
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
          {visitor.customer?.full_name ?? visitor.anonymous_code.replace(/^LIVE_[A-Z0-9]+_/, "")}
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
      <div className="flex flex-col items-end gap-1">
        {visitor.isAtCashier ? (
          <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold bg-red-500 text-white">
            Ở QUẦY
          </span>
        ) : (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
            visitor.person_type === "identified"
              ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400"
              : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
          }`}>
            {visitor.person_type === "identified" ? "Đã nhận diện" : "Ẩn danh"}
          </span>
        )}
      </div>
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
      await linkProfileToCustomer({ 
          person_profile_id: visitor.profile_id, 
          customer_id: selectedCustomer.id,
          ai_session_code: visitor.anonymous_code
      });
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

    const phoneValue = newPhone.trim();
    if (!phoneValue) { 
      toast.error("Vui lòng nhập số điện thoại"); 
      return; 
    }
    
    // Regex giống hệt Backend: Bắt đầu bằng 0 hoặc +84, đầu số 3,5,7,8,9 và 8 chữ số tiếp theo
    const phoneRegex = /^(0|\+84)[35789][0-9]{8}$/;
    if (!phoneRegex.test(phoneValue)) {
      toast.error("Số điện thoại không đúng định dạng Việt Nam");
      return;
    }

    setCreating(true);
    try {
      // 1. Gọi API tạo khách thật (Đảm bảo API này trả về data chứa ID từ Database)
      const realCustomer = await createCustomer({
        full_name: newName.trim(),
        phone: newPhone.trim() || undefined,
        gender: newGender,
        person_profile_id: visitor.profile_id > 0 ? visitor.profile_id : undefined,
        ai_session_code: visitor.anonymous_code
      });

      toast.success(`Đã tạo khách hàng "${newName}"`);
      
      // 2. lấy realCustomer.id (do Backend trả về) để gán vào state.
      onSuccess({ 
        ...visitor, 
        person_type: "identified", 
        customer: {
          id: realCustomer.id, // DÙNG ID THẬT Ở ĐÂY!
          customer_code: realCustomer.customer_code ?? "",
          full_name: realCustomer.full_name,
          phone: realCustomer.phone ?? null,
        }
      });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || e.message || "Tạo khách hàng thất bại");
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
          <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>{visitor.anonymous_code.replace(/^LIVE_[A-Z0-9]+_/, "")}</p>
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
            placeholder="Nhập số điện thoại khách hàng..."
            value={search}
            onChange={(e) => {
              // BẢN VÁ: Chỉ cho phép nhập số (loại bỏ mọi ký tự không phải số)
              const onlyNums = e.target.value.replace(/\D/g, "");
              setSearch(onlyNums);
            }}
            leftIcon={<Search className="h-4 w-4" />}
            maxLength={11} // Giới hạn độ dài SĐT tối đa
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
                    {/* BẢN VÁ: Nhấn mạnh vào số điện thoại thay vì mã khách hàng */}
                    <p className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{c.phone ?? "Chưa cập nhật SĐT"}</p>
                  </div>
                  {selectedCustomer?.id === c.id && <CheckCircle2 className="h-4 w-4 text-amber-500 shrink-0" />}
                </button>
              ))}
            </div>
          )}
          {!searchLoading && search && customers.length === 0 && (
            <p className="py-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>Không tìm thấy khách hàng với SĐT này</p>
          )}
          {!search && (
            <p className="py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>Vui lòng nhập số điện thoại để tìm kiếm</p>
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
            <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
              Số điện thoại <span className="text-red-500">*</span>
            </label>
            <Input 
              value={newPhone} 
              onChange={(e) => {
                // Tùy chọn: Tự động loại bỏ các ký tự không phải số hoặc dấu + (ngăn nhập chữ)
                const cleanedValue = e.target.value.replace(/[^\d+]/g, '');
                setNewPhone(cleanedValue);
              }} 
              placeholder="0901234567" 
              maxLength={12} 
            />
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
        // person_profile_id: visitor.profile_id,
        person_profile_id: visitor.profile_id > 0 ? visitor.profile_id : null,
        customer_id: visitor.customer?.id ?? null,
        total_amount: numAmount,
        item_summary: description.trim() || undefined,
        payment_method: paymentMethod,
        ai_session_code: visitor.anonymous_code,
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
            {visitor.customer?.full_name ?? visitor.anonymous_code.replace(/^LIVE_[A-Z0-9]+_/, "")}
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
  const toast = useToast(); // Vẫn giữ để xài cho phần API form (tạo đơn, link user)

  // const [visitors, setVisitors] = useState<(InStoreVisitor & { isAtCashier?: boolean })[]>([]);
  const [visitors, setVisitors] = useState<(InStoreVisitor & { 
    isAtCashier?: boolean;
    entry_video_time?: number;
    latest_video_time?: number;
  })[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  
  const lastUpdateRef = useRef<number>(0);

  const firstSourceTimeRef = useRef<number | null>(null);
  const startRealTimeRef = useRef<number | null>(null);
  const eventQueueRef = useRef<any[]>([]); // Hàng đợi chứa các sự kiện chưa tới giờ diễn ra
  const syncTickerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selected = visitors.find((v) => v.session_id === selectedId) ?? null;

  // === 1. BỔ SUNG REF LƯU TỌA ĐỘ TỪ API ===
  const cashierZoneRef = useRef<Point[]>([]);

  // === 2. BỔ SUNG EFFECT GỌI API ===
  useEffect(() => {
    async function fetchCashierZone() {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        
        // Nối apiUrl vào trước đường dẫn
        const response = await fetch(`${apiUrl}/api/store-zones?type=cashier`);
        if (!response.ok) return;

        const data = await response.json();
        // Giả sử API trả về { polygon: [{x: 0.6, y: 0.5}, ...] }
        if (data?.polygon?.length >= 3) {
          cashierZoneRef.current = data.polygon;
        }
      } catch (error) {
        console.error("Lỗi tải tọa độ quầy thu ngân:", error);
      }
    }
    fetchCashierZone();
  }, []);

  const fetchVisitors = useCallback(async (silent = false) => {
    const timeSinceLastFrame = Date.now() - lastUpdateRef.current;
    
    // Nếu video đang chạy mượt mà (vừa có frame trong 3 giây qua) -> Bỏ qua API để tránh nhiễu
    if (timeSinceLastFrame < 3000) return;

    if (!silent) setLoading(true);
    try {
      const { data } = await getInStoreVisitors(); 
      
      setVisitors((prev) => {
        // 1. Ghép data từ DB với state hiện tại (áp dụng cho khách cũ)
        const mergedFromApi = data.map((newVisitor) => {
          const existing = prev.find((p) => 
            p.anonymous_code === newVisitor.anonymous_code || 
            p.session_id === newVisitor.session_id
          );
          
          return { 
            ...newVisitor, 
            isAtCashier: existing?.isAtCashier || false,
            entry_video_time: existing?.entry_video_time, 
            latest_video_time: existing?.latest_video_time,
            face_image_url: existing?.face_image_url || newVisitor.face_image_url,
            person_type: existing?.person_type === "identified" ? "identified" : newVisitor.person_type
          };
        });

        // 2. CHỐT CHẶN DỌN DẸP THÔNG MINH
        // Nếu video chỉ mới tạm dừng (< 10 giây), tiếp tục giữ lại khách ảo của AI
        if (timeSinceLastFrame < 10000) {
            const wsOnlyVisitors = prev.filter(
              (p) => !data.some((d) => d.anonymous_code === p.anonymous_code || d.session_id === p.session_id)
            );
            return [...mergedFromApi, ...wsOnlyVisitors];
        }
        
        // Nếu video đã kết thúc (ngưng quá 10 giây), quét sạch bóng ma AI, chỉ dùng data từ DB
        return mergedFromApi;
      });
    } catch (e) {
      if (!silent) toast.error("Không tải được danh sách khách");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [toast]);

  // Initial load + polling + WebSocket setup
  // ==========================================
  // EFFECT 1: Dành riêng cho Polling API
  // ==========================================
  useEffect(() => {
    fetchVisitors();
    pollRef.current = setInterval(() => fetchVisitors(true), POLL_INTERVAL);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchVisitors]);


  // ==========================================
  // EFFECT 2: Dành riêng cho WebSocket Realtime (Sử dụng Queue Buffer)
  // ==========================================
  useEffect(() => {
    if (wsRef.current) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsUrl}/api/cashier/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("✅ [Thu Ngân] WebSocket đã kết nối!");
      eventQueueRef.current = [];
    };

    // 1. WebSocket chỉ làm đúng 1 việc: Nhận data AI và tống vào hàng chờ
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "detection") {
           eventQueueRef.current.push(msg.data);
        }
      } catch (e) {
        console.error("Lỗi parse WS", e);
      }
    };

    // 2. Kênh Lắng nghe Video: Mọi thứ tự động chạy theo nhịp độ của video
    const channel = new BroadcastChannel("video_sync");
    
    channel.onmessage = (e) => {
      const currentVideoTime = e.data; // Thời gian video lấy từ StreamingOverlay

      const now = Date.now();
      // Nếu chưa qua 300ms kể từ lần cập nhật trước, bỏ qua để nhường CPU cho Video vẽ khung
      if (now - lastUpdateRef.current < 300) return; 
      // Cập nhật lại mốc thời gian
      lastUpdateRef.current = now;
      
      const queue = eventQueueRef.current;
      if (queue.length === 0) return;

      // Xả hàng: Chỉ lấy những sự kiện có source_timestamp_seconds nhỏ hơn hoặc bằng thời gian video hiện tại
     const readyItems = queue.filter(item => (item.source_timestamp_seconds || 0) <= currentVideoTime);
      
      eventQueueRef.current = queue.filter(item => (item.source_timestamp_seconds || 0) > currentVideoTime);

      if (readyItems.length > 0) {
        setVisitors((prev) => {
          let updatedList = [...prev];

          readyItems.forEach((detectionData) => {
            // Chỉ xử lý và hiển thị những khuôn mặt rõ nét (confidence >= 50%)
            if ((detectionData.confidence || 0) < 0.50) return;
            const code = String(detectionData.anonymous_code || "");
            const realtimeSessionId = -Number(detectionData.track_id);
            
            const [x1, y1, x2, y2] = detectionData.bbox || [0, 0, 0, 0];
            const feetX = (x1 + x2) / 2;
            const feetY = y2;
            //const atCashier = isPointInPolygon({ x: feetX, y: feetY }, CASHIER_ZONE);
            const currentZone = cashierZoneRef.current;
            const atCashier = currentZone.length >= 3 
              ? isPointInPolygon({ x: feetX, y: feetY }, currentZone) 
              : false;

            const index = updatedList.findIndex((v) => 
               v.session_id === realtimeSessionId || 
               v.anonymous_code === code || 
               (detectionData.session_profile_id && v.anonymous_code === detectionData.session_profile_id)
            );

            if (index >= 0) {
              // Gộp TẤT CẢ các trường có thể chứa ảnh từ AI để không bị sót
              const newAvatar = detectionData.face_crop_url 
                             || detectionData.current_video_avatar 
                             || detectionData.identified_customer_avatar 
                             || detectionData.stored_profile_avatar;

              updatedList[index] = { 
                ...updatedList[index], 
                isAtCashier: atCashier,
                // Ưu tiên cập nhật ảnh mới, nếu không có mới dùng lại ảnh cũ
                face_image_url: newAvatar || updatedList[index].face_image_url,
                // Nâng cấp trạng thái nếu AI nhận diện ra người quen
                person_type: detectionData.customer_id ? "identified" : updatedList[index].person_type,
                latest_video_time: detectionData.source_timestamp_seconds,
              };

              // Cập nhật tên thật nếu AI nhận ra (từ ANON -> identified)
              if (detectionData.customer_id) {
                 updatedList[index].customer = {
                    id: detectionData.customer_id,
                    full_name: detectionData.customer_name,
                    customer_code: detectionData.customer_code,
                    phone: null
                 };
              }

              if (/^(?:LIVE_.*_)?(P|ANON)_\d+$/i.test(code)) {
                updatedList[index].anonymous_code = code;
              }
            } else {
              if (/^(?:LIVE_.*_)?(P|ANON)_\d+$/i.test(code)) {
                 updatedList.push({
                    session_id: realtimeSessionId,
                    entry_time: new Date().toISOString(),
                    profile_id: realtimeSessionId,
                    anonymous_code: code,
                    person_type: (detectionData.customer_id ? "identified" : "anonymous") as "identified" | "anonymous",
                    face_image_url: detectionData.face_crop_url 
                                 || detectionData.current_video_avatar 
                                 || detectionData.identified_customer_avatar 
                                 || detectionData.stored_profile_avatar 
                                 || null,
                    customer: detectionData.customer_id ? {
                       id: detectionData.customer_id,
                       full_name: detectionData.customer_name,
                       customer_code: "N/A",
                       phone: null
                    } : null,
                    isAtCashier: atCashier,
                    entry_video_time: detectionData.source_timestamp_seconds,
                    latest_video_time: detectionData.source_timestamp_seconds,
                 } as any);
              }
            }
          });
          updatedList = updatedList.filter(v => {
            if (v.latest_video_time !== undefined) {
               // Xóa ngay những ai không xuất hiện trong camera quá 2 giây
               return (currentVideoTime - v.latest_video_time) < 2.0;
            }
            // Khách từ DB (không có dữ liệu live): Xóa luôn nhường chỗ cho AI quét
            return false; 
          });
          return updatedList;
        });
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      channel.close();
    };
  }, []);

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
    setVisitors((prev) => prev.map((v) => v.session_id === updated.session_id ? { ...updated, isAtCashier: v.isAtCashier } : v));
  }

  function handleOrderSuccess() {
    setSelectedId(null);
    fetchVisitors(true);
  }

  const identified = visitors.filter((v) => v.person_type === "identified").length;
  const anonymous = visitors.filter((v) => v.person_type === "anonymous").length;
  const realtimeTotal = visitors.length

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
          { label: "Đang trong cửa hàng", value: realtimeTotal,  color: "text-amber-600 dark:text-amber-400",   bg: "bg-amber-50 dark:bg-amber-500/10",   icon: <Users className="h-5 w-5" /> },
          { label: "Đã nhận diện",         value: identified,     color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10", icon: <UserCheck className="h-5 w-5" /> },
          { label: "Ẩn danh",              value: anonymous,      color: "text-slate-600 dark:text-slate-400",   bg: "bg-slate-100 dark:bg-slate-800",       icon: <Users className="h-5 w-5" /> },
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
              Danh sách khách ({realtimeTotal})
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
                {/* Sort ưu tiên người đang ở quầy lên đầu */}
                {[...visitors].sort((a, b) => (b.isAtCashier ? 1 : 0) - (a.isAtCashier ? 1 : 0)).map((v) => (
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