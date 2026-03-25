"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  Plane, Hotel, Shield, Calendar, MessageSquare, Receipt, FileText,
  Loader2, CheckCircle2, XCircle, ArrowRight, Send, MapPin,
} from "lucide-react";

interface StepState {
  status: "idle" | "sending" | "waiting" | "approved" | "denied" | "auto" | "skipped";
  detail?: string;
  jobId?: string;
  cost?: number;
}

const DESTINATIONS = [
  { value: "berlin", label: "Berlin", visa: false },
  { value: "london", label: "London", visa: false },
  { value: "new york", label: "New York", visa: true },
  { value: "san francisco", label: "San Francisco", visa: true },
];

const FLIGHTS: Record<string, { economy: number; business: number; airline: string; flight_no: string; duration: string }> = {
  berlin: { economy: 420, business: 1850, airline: "Lufthansa", flight_no: "LH1834", duration: "2h 35m" },
  london: { economy: 350, business: 1400, airline: "British Airways", flight_no: "BA680", duration: "3h 50m" },
  "new york": { economy: 890, business: 3200, airline: "Delta", flight_no: "DL34", duration: "10h 20m" },
  "san francisco": { economy: 950, business: 3800, airline: "United", flight_no: "UA90", duration: "13h 15m" },
};

const HOTELS: Record<string, { name: string; price: number }[]> = {
  berlin: [{ name: "Holiday Inn", price: 95 }, { name: "Motel One", price: 120 }, { name: "Adlon Kempinski", price: 380 }],
  london: [{ name: "Premier Inn", price: 110 }, { name: "The Savoy", price: 520 }],
  "new york": [{ name: "Pod 51", price: 130 }, { name: "The Plaza", price: 650 }],
  "san francisco": [{ name: "HI Downtown", price: 85 }, { name: "Ritz-Carlton", price: 490 }],
};

const stepConfig = [
  { key: "flight", label: "Book Flight", icon: Plane, color: "text-blue-600" },
  { key: "hotel", label: "Reserve Hotel", icon: Hotel, color: "text-purple-600" },
  { key: "insurance", label: "Travel Insurance", icon: Shield, color: "text-green-600" },
  { key: "calendar", label: "Add to Calendar", icon: Calendar, color: "text-orange-600" },
  { key: "slack", label: "Notify Team", icon: MessageSquare, color: "text-pink-600" },
  { key: "expense", label: "Log Expense", icon: Receipt, color: "text-cyan-600" },
  { key: "visa", label: "Visa Check", icon: FileText, color: "text-red-600" },
];

export default function TravelOpsPage() {
  const [traveler, setTraveler] = useState("alice@company.com");
  const [destination, setDestination] = useState("berlin");
  const [purpose, setPurpose] = useState("React Conf 2026");
  const [nights, setNights] = useState(3);
  const [flightClass, setFlightClass] = useState<"economy" | "business">("economy");
  const [hotelIndex, setHotelIndex] = useState(0);
  const [running, setRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [steps, setSteps] = useState<Record<string, StepState>>({});
  const [totalCost, setTotalCost] = useState(0);

  const flight = FLIGHTS[destination] || FLIGHTS.berlin;
  const hotels = HOTELS[destination] || HOTELS.berlin;
  const hotel = hotels[Math.min(hotelIndex, hotels.length - 1)];
  const flightPrice = flightClass === "business" ? flight.business : flight.economy;
  const hotelTotal = hotel.price * nights;
  const destInfo = DESTINATIONS.find(d => d.value === destination);

  const updateStep = (key: string, state: StepState) => {
    setSteps(prev => ({ ...prev, [key]: state }));
  };

  const sendAndPoll = async (connection: string, action: string, params: Record<string, any>): Promise<"approved" | "denied" | "auto"> => {
    try {
      const res = await api.sendTestRequest({ connection, action, params });
      if (res.status === "auto_approved") return "auto";
      if (!res.job_id) return "auto";

      // Poll
      for (let i = 0; i < 100; i++) {
        await new Promise(r => setTimeout(r, 2000));
        try {
          const s = await api.getJobStatus(res.job_id);
          if (s.status === "approved") return "approved";
          if (s.status === "rejected") return "denied";
          if (s.status === "timeout") return "denied";
          if (s.status === "blocked") return "denied";
        } catch {}
      }
      return "denied";
    } catch {
      return "denied";
    }
  };

  const runTrip = async () => {
    setRunning(true);
    setTotalCost(0);
    setSteps({});
    let cost = 0;

    // Step 1: Flight
    setCurrentStep(0);
    updateStep("flight", { status: "sending", cost: flightPrice });
    updateStep("flight", { status: "waiting", detail: `${flight.airline} ${flight.flight_no} — $${flightPrice}`, cost: flightPrice });

    const flightResult = await sendAndPoll("stripe-prod", "charge", {
      amount_usd: flightPrice, customer: traveler,
      description: `Flight ${flight.flight_no} to ${destination} (${flightClass})`,
    });

    if (flightResult === "denied") {
      updateStep("flight", { status: "denied", detail: "Flight denied — trip cancelled", cost: flightPrice });
      setRunning(false);
      return;
    }
    cost += flightPrice;
    updateStep("flight", { status: flightResult === "auto" ? "auto" : "approved", detail: `${flight.airline} ${flight.flight_no}`, cost: flightPrice });

    // Step 2: Hotel
    setCurrentStep(1);
    updateStep("hotel", { status: "waiting", detail: `${hotel.name} — $${hotel.price}/night x ${nights}`, cost: hotelTotal });

    const hotelResult = await sendAndPoll("stripe-prod", "charge", {
      amount_usd: hotelTotal, customer: traveler,
      description: `Hotel ${hotel.name} ${nights}n in ${destination}`,
    });

    if (hotelResult === "denied") {
      updateStep("hotel", { status: "denied", detail: "Hotel denied", cost: hotelTotal });
    } else {
      cost += hotelTotal;
      updateStep("hotel", { status: hotelResult === "auto" ? "auto" : "approved", detail: `${hotel.name} — ${nights} nights`, cost: hotelTotal });
    }

    // Step 3: Insurance
    setCurrentStep(2);
    const insuranceCost = 29;
    updateStep("insurance", { status: "waiting", detail: "Basic Travel Cover — $29", cost: insuranceCost });

    const insResult = await sendAndPoll("stripe-prod", "charge", {
      amount_usd: insuranceCost, customer: traveler,
      description: "Travel insurance: Basic Travel Cover",
    });
    cost += insuranceCost;
    updateStep("insurance", { status: insResult === "denied" ? "denied" : "auto", detail: "Basic Travel Cover ($50,000)", cost: insuranceCost });

    // Step 4: Calendar (auto)
    setCurrentStep(3);
    updateStep("calendar", { status: "auto", detail: `${purpose} — ${destination}` });

    // Step 5: Slack
    setCurrentStep(4);
    updateStep("slack", { status: "waiting", detail: `Posting to #travel` });
    const slackResult = await sendAndPoll("slack-prod", "send_message", {
      channel: "#travel",
      message: `${traveler} traveling to ${destination} for ${purpose}`,
    });
    updateStep("slack", { status: slackResult === "denied" ? "denied" : "auto", detail: "#travel notified" });

    // Step 6: Expense (auto)
    setCurrentStep(5);
    updateStep("expense", { status: "auto", detail: `$${cost} logged`, cost });

    // Step 7: Visa
    setCurrentStep(6);
    if (destInfo?.visa) {
      updateStep("visa", { status: "waiting", detail: "Visa required — sending reminder" });
      await sendAndPoll("gmail-prod", "send_email", {
        recipient: traveler, subject: `Visa reminder: ${destination}`,
        body: `Your trip to ${destination} requires a visa.`, type: "visa_reminder",
      });
      updateStep("visa", { status: "auto", detail: "Reminder sent" });
    } else {
      updateStep("visa", { status: "skipped", detail: "Not required" });
    }

    setTotalCost(cost);
    setCurrentStep(7);
    setRunning(false);
  };

  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <Plane className="h-6 w-6 text-blue-600" />
          <h1 className="text-2xl font-bold text-zinc-900">TravelOps Agent</h1>
        </div>
        <p className="text-zinc-500">Corporate travel manager — book flights, hotels, insurance with human approval</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trip Config */}
        <Card>
          <CardHeader><CardTitle className="text-sm">Trip Details</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-xs font-medium text-zinc-500">Traveler</label>
              <Input value={traveler} onChange={e => setTraveler(e.target.value)} className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-500">Destination</label>
              <Select value={destination} onChange={e => { setDestination(e.target.value); setHotelIndex(0); }} className="mt-1">
                {DESTINATIONS.map(d => <option key={d.value} value={d.value}>{d.label} {d.visa ? "(visa)" : ""}</option>)}
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-500">Purpose</label>
              <Input value={purpose} onChange={e => setPurpose(e.target.value)} className="mt-1" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-zinc-500">Nights</label>
                <Input type="number" min={1} max={14} value={nights} onChange={e => setNights(parseInt(e.target.value) || 1)} className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-500">Class</label>
                <Select value={flightClass} onChange={e => setFlightClass(e.target.value as any)} className="mt-1">
                  <option value="economy">Economy</option>
                  <option value="business">Business</option>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-500">Hotel</label>
              <Select value={String(hotelIndex)} onChange={e => setHotelIndex(parseInt(e.target.value))} className="mt-1">
                {hotels.map((h, i) => <option key={i} value={String(i)}>{h.name} — ${h.price}/night</option>)}
              </Select>
            </div>

            <div className="border-t border-zinc-200 pt-3">
              <div className="flex justify-between text-sm text-zinc-600">
                <span>Flight</span><span>${flightPrice}</span>
              </div>
              <div className="flex justify-between text-sm text-zinc-600">
                <span>Hotel ({nights}n)</span><span>${hotelTotal}</span>
              </div>
              <div className="flex justify-between text-sm text-zinc-600">
                <span>Insurance</span><span>$29</span>
              </div>
              <div className="flex justify-between text-sm font-semibold text-zinc-900 border-t border-zinc-200 pt-2 mt-2">
                <span>Estimated Total</span><span>${flightPrice + hotelTotal + 29}</span>
              </div>
            </div>

            <Button onClick={runTrip} disabled={running} className="w-full">
              {running ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Running trip...</> : <><Send className="h-4 w-4 mr-2" />Book Trip</>}
            </Button>
          </CardContent>
        </Card>

        {/* Live Steps */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                {running ? "Booking in progress..." : currentStep >= 7 ? `Trip booked — $${totalCost}` : "Configure and click Book Trip"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {stepConfig.map((cfg, idx) => {
                  const step = steps[cfg.key];
                  const isActive = currentStep === idx;
                  const isDone = step && ["approved", "auto", "denied", "skipped"].includes(step.status);

                  return (
                    <div key={cfg.key} className={`flex items-start gap-4 p-3 rounded-lg border transition-all ${
                      isActive ? "border-blue-200 bg-blue-50" :
                      isDone ? "border-zinc-200 bg-white" :
                      "border-zinc-100 bg-zinc-50/50 opacity-50"
                    }`}>
                      {/* Step indicator */}
                      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                        step?.status === "approved" ? "bg-green-100" :
                        step?.status === "auto" ? "bg-green-100" :
                        step?.status === "denied" ? "bg-red-100" :
                        step?.status === "skipped" ? "bg-zinc-100" :
                        isActive ? "bg-blue-100" :
                        "bg-zinc-100"
                      }`}>
                        {step?.status === "approved" || step?.status === "auto" ? (
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                        ) : step?.status === "denied" ? (
                          <XCircle className="h-4 w-4 text-red-600" />
                        ) : isActive ? (
                          <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
                        ) : (
                          <cfg.icon className={`h-4 w-4 ${isDone ? "text-zinc-400" : cfg.color}`} />
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className={`text-sm font-medium ${isDone || isActive ? "text-zinc-900" : "text-zinc-400"}`}>
                            {cfg.label}
                          </span>
                          <div className="flex items-center gap-2">
                            {step?.cost && <span className="text-xs font-mono text-zinc-500">${step.cost}</span>}
                            {step?.status === "approved" && <Badge variant="success" className="text-xs">Guardian Approved</Badge>}
                            {step?.status === "auto" && <Badge variant="default" className="text-xs">Auto</Badge>}
                            {step?.status === "denied" && <Badge variant="danger" className="text-xs">Denied</Badge>}
                            {step?.status === "waiting" && <Badge variant="info" className="text-xs"><Loader2 className="h-3 w-3 mr-1 animate-spin" />Waiting for Guardian</Badge>}
                            {step?.status === "skipped" && <Badge variant="default" className="text-xs">Skipped</Badge>}
                          </div>
                        </div>
                        {step?.detail && (
                          <p className="text-xs text-zinc-500 mt-0.5">{step.detail}</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Summary */}
              {currentStep >= 7 && (
                <div className="mt-6 p-4 bg-zinc-900 rounded-lg text-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold">Trip Summary</span>
                    <span className="text-lg font-bold">${totalCost}</span>
                  </div>
                  <div className="text-xs text-zinc-400 space-y-1">
                    <div className="flex justify-between">
                      <span>{traveler}</span>
                      <span>{destination.charAt(0).toUpperCase() + destination.slice(1)} — {purpose}</span>
                    </div>
                    <div className="flex gap-2 mt-2">
                      {Object.entries(steps).map(([key, s]) => (
                        <span key={key} className={`px-1.5 py-0.5 rounded text-xs ${
                          s.status === "approved" || s.status === "auto" ? "bg-green-900 text-green-300" :
                          s.status === "denied" ? "bg-red-900 text-red-300" :
                          "bg-zinc-700 text-zinc-400"
                        }`}>{key}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
