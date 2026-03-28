"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Approver } from "@/types";
import { Plus, Pencil, Trash2, UserCheck, ChevronDown, ChevronUp, ChevronRight, X, Link2, CheckCircle2 } from "lucide-react";
import { FormError } from "@/components/ui/form-error";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

type FormMode = "create" | "edit" | null;

const emptyForm = {
  name: "",
  email: "",
  auth0_user_id: "",
  blackout_start: "",
  blackout_end: "",
};

function ApproversContent() {
  const searchParams = useSearchParams();
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linkedName, setLinkedName] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<FormMode>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Delegation form state
  const [delegatingId, setDelegatingId] = useState<string | null>(null);
  const [delegateTo, setDelegateTo] = useState("");
  const [delegateFrom, setDelegateFrom] = useState("");
  const [delegateUntil, setDelegateUntil] = useState("");
  const [delegateSaving, setDelegateSaving] = useState(false);

  const loadApprovers = () => {
    setLoading(true);
    api.getApprovers()
      .then(setApprovers)
      .catch((e) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadApprovers();
    const linked = searchParams.get("linked");
    const err = searchParams.get("error");
    if (linked) setLinkedName(linked);
    if (err) setError(`Link failed: ${err.replace(/_/g, " ")}`);
  }, []);

  const handleLinkAccount = async (id: string) => {
    try {
      const { url } = await api.getLinkUrl(id);
      window.location.href = url;
    } catch (e: any) {
      setError(e.message || "Failed to get link URL");
    }
  };

  const openCreate = () => {
    setForm(emptyForm);
    setEditId(null);
    setFormMode("create");
    setFormError(null);
  };

  const openEdit = (a: Approver) => {
    setForm({
      name: a.name,
      email: a.email,
      auth0_user_id: a.auth0_user_id,
      blackout_start: a.blackout_start ?? "",
      blackout_end: a.blackout_end ?? "",
    });
    setEditId(a.id);
    setFormMode("edit");
    setFormError(null);
  };

  const closeForm = () => { setFormMode(null); setEditId(null); };

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError("Name is required."); return; }
    if (!form.email.trim()) { setFormError("Email is required."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { setFormError("Please enter a valid email address."); return; }
    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: form.name,
        email: form.email,
        auth0_user_id: form.auth0_user_id,
        blackout_start: form.blackout_start || null,
        blackout_end: form.blackout_end || null,
        notify_channel: ["guardian_push"],
        urgent_channel: ["guardian_push"],
      };
      if (formMode === "edit" && editId) {
        await api.updateApprover(editId, payload);
      } else {
        await api.createApprover(payload);
      }
      closeForm();
      loadApprovers();
    } catch (e: any) {
      setFormError(e.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this approver? This cannot be undone.")) return;
    try {
      await api.deleteApprover(id);
      loadApprovers();
    } catch (e: any) {
      setError(e.message || "Failed to delete");
    }
  };

  const handleDelegate = async (approver: Approver) => {
    if (!delegateTo || !delegateFrom || !delegateUntil) {
      return;
    }
    setDelegateSaving(true);
    try {
      await api.setDelegation(approver.id, {
        delegate_to: delegateTo,
        delegate_from: delegateFrom,
        delegate_until: delegateUntil,
      });
      setDelegatingId(null);
      loadApprovers();
    } catch (e: any) {
      setError(e.message || "Failed to set delegation");
    } finally {
      setDelegateSaving(false);
    }
  };

  const approverName = (id: string) =>
    approvers.find((a) => a.id === id)?.name ?? id.slice(0, 8);

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">

        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Approvers</h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1">Manage who can approve agent actions</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" /> Add Approver
        </Button>
      </div>

      {linkedName && (
        <div className="mb-4 p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400 flex justify-between items-center">
          <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4" /><strong>{linkedName}</strong> linked to Auth0 account — Guardian push enabled.</span>
          <button onClick={() => setLinkedName(null)}><X className="h-4 w-4" /></button>
        </div>
      )}
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 rounded-lg text-sm text-red-700 dark:text-red-400 flex justify-between">
          {error}
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Create / Edit Form */}
      {formMode && (
        <Card className="mb-6 border-zinc-300 dark:border-zinc-600">
          <CardHeader>
            <CardTitle>{formMode === "create" ? "Add Approver" : "Edit Approver"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Name</label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Alice Smith" className="mt-1" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Email</label>
                <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="alice@company.com" className="mt-1" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Blackout Start</label>
                <Input type="time" value={form.blackout_start} onChange={(e) => setForm({ ...form, blackout_start: e.target.value })} className="mt-1" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Blackout End</label>
                <Input type="time" value={form.blackout_end} onChange={(e) => setForm({ ...form, blackout_end: e.target.value })} className="mt-1" />
              </div>
            </div>
            <FormError message={formError} />
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={closeForm}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving…" : formMode === "create" ? "Add Approver" : "Save Changes"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Approvers List */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : approvers.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <UserCheck className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
            <p className="text-zinc-500 dark:text-zinc-400">No approvers yet.</p>
            <Button className="mt-4" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" /> Add First Approver
            </Button>
          </CardContent>
        </Card>
      ) : (
        <ApproversList approvers={approvers} expandedId={expandedId} setExpandedId={setExpandedId}
          approverName={approverName} handleLinkAccount={handleLinkAccount} openEdit={openEdit}
          handleDelete={handleDelete} delegatingId={delegatingId} setDelegatingId={setDelegatingId}
          delegateTo={delegateTo} setDelegateTo={setDelegateTo}
          delegateFrom={delegateFrom} setDelegateFrom={setDelegateFrom}
          delegateUntil={delegateUntil} setDelegateUntil={setDelegateUntil}
          delegateSaving={delegateSaving} handleDelegate={handleDelegate}
          loadApprovers={loadApprovers} setError={setError}
        />
      )}
    </div>
  );
}

function ApproversList({ approvers, expandedId, setExpandedId, approverName, handleLinkAccount, openEdit, handleDelete, delegatingId, setDelegatingId, delegateTo, setDelegateTo, delegateFrom, setDelegateFrom, delegateUntil, setDelegateUntil, delegateSaving, handleDelegate, loadApprovers, setError }: any) {
  const [showDemo, setShowDemo] = useState(false);
  const isDemoApprover = (a: Approver) => a.email?.endsWith("@demo.approvalkit.io");
  const userApprovers = approvers.filter((a: Approver) => !isDemoApprover(a));
  const demoApprovers = approvers.filter((a: Approver) => isDemoApprover(a));

  const renderApprover = (a: Approver) => (
            <Card key={a.id} className="hover:border-zinc-300 dark:border-zinc-600 transition-colors">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center font-bold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 text-sm">
                      {a.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-zinc-900 dark:text-zinc-100">{a.name}</span>
                        {a.delegate_to && (
                          <Badge variant="warning">Delegating → {approverName(a.delegate_to)}</Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-sm text-zinc-500 dark:text-zinc-400">{a.email}</span>
                        {a.auth0_user_id ? (
                          <span className="inline-flex items-center gap-1 text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 px-1.5 py-0.5 rounded">
                            <CheckCircle2 className="h-3 w-3" /> Guardian linked
                          </span>
                        ) : (
                          <span className="text-xs text-zinc-400 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 px-1.5 py-0.5 rounded">Not linked</span>
                        )}
                      </div>
                      {(a.blackout_start || a.notify_channel?.length > 0) && (
                        <div className="flex items-center gap-2 mt-1">
                          {a.blackout_start && (
                            <Badge variant="default">
                              Blackout {a.blackout_start}–{a.blackout_end}
                            </Badge>
                          )}
                          {a.notify_channel?.map((ch) => (
                            <Badge key={ch} variant="info">{ch}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!a.auth0_user_id && (
                      <Button size="sm" variant="outline" onClick={() => handleLinkAccount(a.id)}>
                        <Link2 className="h-3.5 w-3.5 mr-1" /> Link Account
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
                    >
                      Delegate {expandedId === a.id ? <ChevronUp className="h-4 w-4 ml-1" /> : <ChevronDown className="h-4 w-4 ml-1" />}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(a)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 dark:text-red-400 hover:bg-red-50 dark:bg-red-950/30" onClick={() => handleDelete(a.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Delegation Panel */}
                {expandedId === a.id && (
                  <div className="mt-4 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                    {a.delegate_to ? (
                      <div className="flex items-center justify-between">
                        <div className="text-sm text-zinc-600 dark:text-zinc-400">
                          Currently delegating to <strong>{approverName(a.delegate_to)}</strong>
                          {a.delegate_from && (
                            <span className="ml-2 text-zinc-400">
                              {new Date(a.delegate_from).toLocaleDateString()} → {a.delegate_until ? new Date(a.delegate_until).toLocaleDateString() : "∞"}
                            </span>
                          )}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={async () => {
                            try {
                              await api.removeDelegation(a.id);
                              loadApprovers();
                            } catch (e: any) {
                              setError(e.message || "Failed to remove delegation");
                            }
                          }}
                        >
                          Remove Delegation
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Set Delegation</p>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div>
                            <label className="text-xs text-zinc-500 dark:text-zinc-400">Delegate To</label>
                            <select
                              value={delegatingId === a.id ? delegateTo : ""}
                              onChange={(e) => { setDelegatingId(a.id); setDelegateTo(e.target.value); }}
                              className="mt-1 w-full rounded-md border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
                            >
                              <option value="">Select approver…</option>
                              {approvers.filter((x: Approver) => x.id !== a.id).map((x: Approver) => (
                                <option key={x.id} value={x.id}>{x.name}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-xs text-zinc-500 dark:text-zinc-400">From</label>
                            <Input type="datetime-local" className="mt-1" value={delegatingId === a.id ? delegateFrom : ""} onChange={(e) => { setDelegatingId(a.id); setDelegateFrom(e.target.value); }} />
                          </div>
                          <div>
                            <label className="text-xs text-zinc-500 dark:text-zinc-400">Until</label>
                            <Input type="datetime-local" className="mt-1" value={delegatingId === a.id ? delegateUntil : ""} onChange={(e) => { setDelegatingId(a.id); setDelegateUntil(e.target.value); }} />
                          </div>
                        </div>
                        <Button
                          size="sm"
                          disabled={delegateSaving || delegatingId !== a.id || !delegateTo || !delegateFrom || !delegateUntil}
                          onClick={() => handleDelegate(a)}
                        >
                          {delegateSaving ? "Saving…" : "Set Delegation"}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
  );

  return (
    <div className="space-y-3">
      {userApprovers.map(renderApprover)}

      {demoApprovers.length > 0 && (
        <div>
          <button
            onClick={() => setShowDemo(v => !v)}
            className="flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors mb-3 mt-2"
          >
            <ChevronRight className={`h-4 w-4 transition-transform ${showDemo ? "rotate-90" : ""}`} />
            Demo Approvers ({demoApprovers.length})
          </button>
          {showDemo && (
            <div className="space-y-3">
              {demoApprovers.map(renderApprover)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ApproversPage() {
  return (
    <Suspense>
      <ApproversContent />
    </Suspense>
  );
}
