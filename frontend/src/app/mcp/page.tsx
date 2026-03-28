"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Copy, Check, Terminal, Blocks } from "lucide-react";

function CopyBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative group">
      {label && <div className="text-[10px] text-zinc-500 font-mono mb-1">{label}</div>}
      <pre className="bg-zinc-900 text-zinc-100 text-xs rounded-lg p-4 overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
      <button onClick={copy} className="absolute top-2 right-2 p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 opacity-0 group-hover:opacity-100 transition-opacity">
        {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button
      size="sm"
      onClick={copy}
      className={`h-8 px-3 text-xs transition-colors ${
        copied ? "bg-green-600 hover:bg-green-700 text-white" : ""
      }`}
    >
      {copied ? (
        <><Check className="h-3.5 w-3.5 mr-1.5" /> Copied to clipboard</>
      ) : (
        <><Copy className="h-3.5 w-3.5 mr-1.5" /> {label}</>
      )}
    </Button>
  );
}


export default function MCPPage() {
  const claudeCodeCmd = `pip install "approvalkit @ git+https://github.com/yigitcankzl/ApprovalKit.git#subdirectory=sdk" && claude mcp add approvalkit \\
  -e APPROVALKIT_URL=http://localhost:8000 \\
  -e APPROVALKIT_API_KEY=YOUR_API_KEY \\
  -e APPROVALKIT_HMAC_SECRET=YOUR_HMAC_SECRET \\
  -- approvalkit-mcp`;

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
          MCP Server
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-2 text-sm">
          Connect any AI agent to ApprovalKit via Model Context Protocol
        </p>
      </div>

      {/* What is MCP */}
      <Card className="mb-6">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-2">What is MCP?</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
            Model Context Protocol (MCP) is an open standard for connecting AI models to external tools and data.
            ApprovalKit exposes 5 MCP tools that any compatible agent can use to request human approval before
            executing high-risk actions. The agent never holds credentials — Token Vault executes after approval.
          </p>
          <div className="flex flex-wrap gap-2 mt-3">
            <Badge variant="default">request_approval</Badge>
            <Badge variant="default">check_approval_status</Badge>
            <Badge variant="default">wait_for_approval</Badge>
            <Badge variant="default">list_connections</Badge>
            <Badge variant="default">list_rules</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Credentials note */}
      <Card className="mb-6">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-2">Credentials</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Replace <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">YOUR_API_KEY</code> and <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">YOUR_HMAC_SECRET</code> with your actual keys.
            Go to <a href="/connect" className="text-blue-500 hover:underline">Connect Agent</a> to get them.
          </p>
        </CardContent>
      </Card>

      {/* Claude Code setup */}
      <div className="space-y-4">
        <Card className="border-green-200 dark:border-green-800">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-1.5 bg-green-100 dark:bg-green-900/30 rounded-lg">
                  <Terminal className="h-4 w-4 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Claude Code (CLI)</h3>
                  <p className="text-xs text-zinc-400">Paste in your terminal to set up</p>
                </div>
              </div>
            </div>
            <CopyBlock code={claudeCodeCmd} label="Terminal" />
            <div className="mt-3 flex items-center gap-3">
              <CopyButton text={claudeCodeCmd} label="Copy command" />
              <span className="text-xs text-zinc-400">Replace keys, paste in terminal, press Enter</span>
            </div>
          </CardContent>
        </Card>

        {/* Available Tools */}
        <Card>
          <CardContent className="p-5">
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-4">Available MCP Tools</h3>
            <div className="space-y-3">
              <ToolDoc
                name="request_approval"
                desc="Request human approval for an action. Returns immediately with a job ID."
                args="connection, action, params, user_id?"
                example='await request_approval("stripe-prod", "charge", {"amount": 500})'
              />
              <ToolDoc
                name="wait_for_approval"
                desc="Request approval and block until resolved. Combines request + polling."
                args="connection, action, params, user_id?, timeout_seconds?"
                example='await wait_for_approval("github-main", "deploy", {"ref": "v2.0", "env": "production"})'
              />
              <ToolDoc
                name="check_approval_status"
                desc="Check status of a pending approval by job ID."
                args="job_id"
                example='await check_approval_status("abc-123-def")'
              />
              <ToolDoc
                name="list_connections"
                desc="List available service connections and their actions."
                args=""
                example="await list_connections()"
              />
              <ToolDoc
                name="list_rules"
                desc="List active approval rules showing what needs approval."
                args=""
                example="await list_rules()"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="h-8" />
    </div>
  );
}

function ToolDoc({ name, desc, args, example }: { name: string; desc: string; args: string; example: string }) {
  return (
    <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-700">
      <div className="flex items-center gap-2 mb-1">
        <code className="text-sm font-semibold text-purple-600 dark:text-purple-400">{name}</code>
        {args && <span className="text-[10px] text-zinc-400">({args})</span>}
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">{desc}</p>
      <pre className="bg-zinc-50 dark:bg-zinc-800/50 text-[11px] text-zinc-600 dark:text-zinc-400 rounded px-2 py-1 overflow-x-auto">
        <code>{example}</code>
      </pre>
    </div>
  );
}
