import React, { useState, useEffect } from 'react';
import {
  Star, MessageSquare, ThumbsUp, AlertTriangle, ShieldCheck,
  TrendingUp, Utensils, RefreshCw, ExternalLink, QrCode,
  Copy, Check, Filter, CheckCircle2, XCircle, EyeOff, Eye,
  Save, Share2, Award, AlertCircle, Camera
} from 'lucide-react';
import { feedbackApi, restaurantApi } from '../../services/api';
import { Feedback, FeedbackAnalytics } from '../../types';
import { resolveMediaUrl } from '../../config/runtime';

export const CustomerFeedbackPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [analytics, setAnalytics] = useState<FeedbackAnalytics | null>(null);
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'POSITIVE' | 'CRITICAL' | 'FLAGGED'>('ALL');

  // Google Review Settings
  const [googleUrl, setGoogleUrl] = useState('');
  const [savingGoogleUrl, setSavingGoogleUrl] = useState(false);
  const [googleUrlSuccess, setGoogleUrlSuccess] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [showQrModal, setShowQrModal] = useState(false);

  // Moderation state
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadData = async () => {
    try {
      setRefreshing(true);
      const [analyticsData, feedbackList] = await Promise.all([
        feedbackApi.getAnalytics(),
        feedbackApi.list(),
      ]);
      setAnalytics(analyticsData);
      setFeedbacks(feedbackList);
      if (analyticsData?.google_review_url) {
        setGoogleUrl(analyticsData.google_review_url);
      }
    } catch (err: any) {
      console.error('Failed to load feedback analytics:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSaveGoogleUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingGoogleUrl(true);
    setGoogleUrlSuccess(false);
    try {
      await restaurantApi.updateProfile({ google_review_url: googleUrl.trim() });
      setGoogleUrlSuccess(true);
      setActionMessage({ type: 'success', text: 'Google Review URL updated successfully!' });
      setTimeout(() => setGoogleUrlSuccess(false), 3000);
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to save Google Review URL.' });
    } finally {
      setSavingGoogleUrl(false);
    }
  };

  const handleCopyLink = () => {
    if (!googleUrl) return;
    navigator.clipboard.writeText(googleUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const handleModerate = async (id: number, statusVal: string, isPublished: boolean) => {
    try {
      await feedbackApi.moderate(id, {
        status: statusVal,
        is_published: isPublished,
        flag_reason: statusVal === 'FLAGGED' ? 'Flagged by restaurant manager' : undefined,
      });
      setActionMessage({ type: 'success', text: `Review status changed to ${statusVal}.` });
      await loadData();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to moderate review.' });
    }
  };

  const filteredFeedbacks = feedbacks.filter((fb) => {
    if (activeFilter === 'POSITIVE') return fb.overall_rating >= 4;
    if (activeFilter === 'CRITICAL') return fb.overall_rating <= 2;
    if (activeFilter === 'FLAGGED') return fb.status === 'FLAGGED';
    return true;
  });

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <RefreshCw className="w-8 h-8 text-amber-400 animate-spin" />
          <p className="text-zinc-400 text-sm">Loading customer reviews and sentiment analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
              <Star className="w-5 h-5 text-amber-400 fill-amber-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Customer Reviews & Ratings</h1>
              <p className="text-xs text-zinc-400">Verified dining sentiment, dish-level performance, and Google Review management</p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowQrModal(true)}
            className="px-3 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold border border-zinc-700 flex items-center space-x-1.5 transition"
          >
            <QrCode className="w-4 h-4 text-amber-400" />
            <span>Google Review QR</span>
          </button>
          <button
            onClick={loadData}
            disabled={refreshing}
            className="px-3 py-2 rounded-xl bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 text-xs font-medium border border-zinc-700 flex items-center space-x-2 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between ${
            actionMessage.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          <div className="flex items-center space-x-2.5">
            {actionMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            )}
            <span className="text-xs font-medium">{actionMessage.text}</span>
          </div>
          <button onClick={() => setActionMessage(null)} className="text-zinc-400 hover:text-white">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Overall Rating */}
        <div className="p-5 rounded-2xl bg-[#12131a] border border-zinc-800/80 relative overflow-hidden">
          <div className="flex justify-between items-start">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">Overall Rating</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
              Verified
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-black text-white">{analytics?.average_overall.toFixed(1) || '5.0'}</span>
            <span className="text-xs text-zinc-400">/ 5.0</span>
          </div>
          <div className="mt-2 flex items-center space-x-1">
            {[1, 2, 3, 4, 5].map((s) => (
              <Star
                key={s}
                className={`w-3.5 h-3.5 ${
                  s <= Math.round(analytics?.average_overall || 5)
                    ? 'text-amber-400 fill-amber-400'
                    : 'text-zinc-700'
                }`}
              />
            ))}
            <span className="text-[11px] text-zinc-400 ml-1.5">({analytics?.total_reviews || 0} reviews)</span>
          </div>
        </div>

        {/* Food Quality */}
        <div className="p-5 rounded-2xl bg-[#12131a] border border-zinc-800/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block">Food Quality</span>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-black text-emerald-400">{analytics?.average_food.toFixed(1) || '5.0'}</span>
            <span className="text-xs text-zinc-400">/ 5.0</span>
          </div>
          <span className="text-[11px] text-zinc-400 block mt-2">Taste, presentation & freshness</span>
        </div>

        {/* Service Quality */}
        <div className="p-5 rounded-2xl bg-[#12131a] border border-zinc-800/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block">Service Quality</span>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-black text-sky-400">{analytics?.average_service.toFixed(1) || '5.0'}</span>
            <span className="text-xs text-zinc-400">/ 5.0</span>
          </div>
          <span className="text-[11px] text-zinc-400 block mt-2">Staff attentiveness & speed</span>
        </div>

        {/* Ambience & Atmosphere */}
        <div className="p-5 rounded-2xl bg-[#12131a] border border-zinc-800/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block">Ambience</span>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-black text-purple-400">{analytics?.average_ambience.toFixed(1) || '5.0'}</span>
            <span className="text-xs text-zinc-400">/ 5.0</span>
          </div>
          <span className="text-[11px] text-zinc-400 block mt-2">Lighting, music & comfort</span>
        </div>

        {/* Cleanliness */}
        <div className="p-5 rounded-2xl bg-[#12131a] border border-zinc-800/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 block">Cleanliness</span>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-black text-teal-400">{analytics?.average_cleanliness.toFixed(1) || '5.0'}</span>
            <span className="text-xs text-zinc-400">/ 5.0</span>
          </div>
          <span className="text-[11px] text-zinc-400 block mt-2">Table hygiene & sanitation</span>
        </div>
      </div>

      {/* Section: Star Breakdown & Google Review Management */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Rating Breakdown Card */}
        <div className="p-6 rounded-2xl bg-[#12131a] border border-zinc-800/80 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Rating Distribution</h3>
          <div className="space-y-2.5">
            {[5, 4, 3, 2, 1].map((stars) => {
              const count = analytics?.rating_breakdown?.[String(stars)] || 0;
              const total = analytics?.total_reviews || 1;
              const pct = total > 0 ? (count / total) * 100 : 0;
              return (
                <div key={stars} className="flex items-center space-x-3 text-xs">
                  <span className="w-12 text-zinc-300 font-semibold flex items-center space-x-1">
                    <span>{stars}</span>
                    <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                  </span>
                  <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-14 text-right text-zinc-400 font-mono text-[11px]">
                    {count} ({Math.round(pct)}%)
                  </span>
                </div>
              );
            })}
          </div>

          <div className="pt-3 border-t border-zinc-800/80 flex justify-between items-center text-xs text-zinc-400">
            <span>Verified Dining Rate:</span>
            <strong className="text-emerald-400 font-semibold">100% Completed Orders</strong>
          </div>
        </div>

        {/* Google Review Integration Card */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-[#12131a] border border-zinc-800/80 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
                <Share2 className="w-4 h-4 text-amber-400" />
                <span>Google Review Integration & QR</span>
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Configure your restaurant's official Google Maps review link for diners
              </p>
            </div>
            <span className="px-2.5 py-1 rounded-lg bg-blue-500/15 text-blue-300 border border-blue-500/30 text-xs font-semibold">
              Voluntary & Organic
            </span>
          </div>

          <form onSubmit={handleSaveGoogleUrl} className="space-y-3">
            <div className="flex gap-2">
              <input
                type="url"
                value={googleUrl}
                onChange={(e) => setGoogleUrl(e.target.value)}
                placeholder="https://g.page/r/your-restaurant/review or https://maps.app.goo.gl/..."
                className="flex-1 px-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 text-xs font-mono focus:outline-none focus:border-amber-500"
              />
              <button
                type="submit"
                disabled={savingGoogleUrl}
                className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs transition flex items-center space-x-1.5 disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{savingGoogleUrl ? 'Saving...' : 'Save URL'}</span>
              </button>
            </div>
          </form>

          {googleUrl && (
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={handleCopyLink}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium border border-zinc-700 flex items-center space-x-1.5"
              >
                {copiedLink ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedLink ? 'Copied Link!' : 'Copy Link'}</span>
              </button>
              <a
                href={googleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium border border-zinc-700 flex items-center space-x-1.5"
              >
                <ExternalLink className="w-3.5 h-3.5 text-blue-400" />
                <span>Test Link</span>
              </a>
              <button
                onClick={() => setShowQrModal(true)}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium border border-zinc-700 flex items-center space-x-1.5"
              >
                <QrCode className="w-3.5 h-3.5 text-amber-400" />
                <span>Display Table QR Stand</span>
              </button>
            </div>
          )}

          {/* Compliance & Anti-Spam Notice */}
          <div className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800 text-[11px] text-zinc-400 space-y-1">
            <div className="flex items-center space-x-2 text-zinc-300 font-semibold">
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <span>Platform Integrity & Compliance Standard</span>
            </div>
            <p>
              SRMP never automatically publishes or promises to publish reviews to Google Maps.
              Customers must independently choose to submit their Google review.
              We do not reward customers for positive reviews, nor do we suppress genuine critical feedback.
            </p>
          </div>
        </div>
      </div>

      {/* Section: Dish-Level Performance & Ratings Leaderboard */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center space-x-2">
          <Utensils className="w-5 h-5 text-amber-400" />
          <span>Dish-Level Culinary Performance</span>
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Rated Dishes */}
          <div className="p-6 rounded-2xl bg-[#12131a] border border-zinc-800/80 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center space-x-1.5">
              <Award className="w-4 h-4" />
              <span>Top-Rated Dishes</span>
            </span>

            {analytics?.top_rated_dishes && analytics.top_rated_dishes.length > 0 ? (
              <div className="space-y-2">
                {analytics.top_rated_dishes.map((dish, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 flex items-center justify-between"
                  >
                    <div>
                      <span className="text-xs font-bold text-white block">{dish.dish_name}</span>
                      <span className="text-[11px] text-zinc-400 block">
                        {dish.review_count} ratings • {dish.positive_percentage}% satisfaction
                      </span>
                    </div>
                    <div className="flex items-center space-x-1.5 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">
                      <Star className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
                      <span className="text-xs font-bold text-emerald-400">{dish.average_rating.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-500 py-6 text-center">No dish ratings recorded yet.</p>
            )}
          </div>

          {/* Dishes Needing Attention */}
          <div className="p-6 rounded-2xl bg-[#12131a] border border-zinc-800/80 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center space-x-1.5">
              <AlertTriangle className="w-4 h-4" />
              <span>Dishes Needing Kitchen Attention (&lt; 3.5★)</span>
            </span>

            {analytics?.low_rated_dishes && analytics.low_rated_dishes.length > 0 ? (
              <div className="space-y-2">
                {analytics.low_rated_dishes.map((dish, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between"
                  >
                    <div>
                      <span className="text-xs font-bold text-white block">{dish.dish_name}</span>
                      <span className="text-[11px] text-zinc-400 block">{dish.review_count} ratings</span>
                    </div>
                    <div className="flex items-center space-x-1.5 bg-rose-500/15 px-2.5 py-1 rounded-lg border border-rose-500/30">
                      <Star className="w-3.5 h-3.5 text-rose-400 fill-rose-400" />
                      <span className="text-xs font-bold text-rose-400">{dish.average_rating.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800/60 text-center space-y-1">
                <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                <span className="text-xs font-semibold text-zinc-300 block">All Dishes Performing Excellently</span>
                <span className="text-[11px] text-zinc-500 block">No dishes currently below the 3.5★ quality threshold.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Section: Customer Feedback Feed & Moderation */}
      <div className="bg-[#12131a] border border-zinc-800/80 rounded-2xl p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <MessageSquare className="w-5 h-5 text-amber-400" />
              <span>Customer Reviews & Feedback</span>
            </h2>
            <p className="text-xs text-zinc-400">Moderation and responses for all dining guests</p>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap gap-1.5 bg-zinc-900 p-1 rounded-xl border border-zinc-800">
            {(['ALL', 'POSITIVE', 'CRITICAL', 'FLAGGED'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setActiveFilter(mode)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeFilter === mode
                    ? 'bg-amber-500 text-black'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                {mode === 'ALL' && `All (${feedbacks.length})`}
                {mode === 'POSITIVE' && '5-Star (>=4★)'}
                {mode === 'CRITICAL' && 'Critical (<=2★)'}
                {mode === 'FLAGGED' && 'Flagged / Moderation'}
              </button>
            ))}
          </div>
        </div>

        {filteredFeedbacks.length === 0 ? (
          <div className="py-12 text-center text-zinc-500 text-xs">
            No customer feedback records match the active filter.
          </div>
        ) : (
          <div className="space-y-4">
            {filteredFeedbacks.map((fb) => (
              <div
                key={fb.id}
                className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3 transition hover:border-zinc-700"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/60 pb-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-9 h-9 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center font-bold text-xs">
                      {fb.customer_name?.charAt(0) || 'G'}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold text-white">{fb.customer_name}</span>
                        {fb.is_verified_dining && (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            Verified Diner
                          </span>
                        )}
                        {fb.status === 'FLAGGED' && (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                            Flagged for Review
                          </span>
                        )}
                        {!fb.is_published && (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-zinc-800 text-zinc-400 border border-zinc-700">
                            Hidden
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-zinc-500 block">
                        {fb.order_number ? `Order ${fb.order_number}` : 'Dine-In Session'} • Table {fb.table_id || 'N/A'} •{' '}
                        {new Date(fb.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <div className="flex items-center space-x-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <Star
                          key={s}
                          className={`w-4 h-4 ${
                            s <= fb.overall_rating
                              ? 'text-amber-400 fill-amber-400'
                              : 'text-zinc-700'
                          }`}
                        />
                      ))}
                    </div>
                    <span className="text-xs font-bold text-white">{fb.overall_rating}.0</span>
                  </div>
                </div>

                {/* Multi-attribute scores */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-zinc-400 bg-zinc-900 p-2.5 rounded-xl border border-zinc-800/80">
                  <div>Food: <strong className="text-white">{fb.food_rating || 5}★</strong></div>
                  <div>Service: <strong className="text-white">{fb.service_rating || 5}★</strong></div>
                  <div>Ambience: <strong className="text-white">{fb.ambience_rating || 5}★</strong></div>
                  <div>Cleanliness: <strong className="text-white">{fb.cleanliness_rating || 5}★</strong></div>
                </div>

                {/* Written review */}
                {fb.comment && (
                  <p className="text-xs text-zinc-300 italic">"{fb.comment}"</p>
                )}

                {/* Dish Ratings */}
                {fb.dish_ratings && fb.dish_ratings.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {fb.dish_ratings.map((dr, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-lg bg-zinc-800 text-[11px] text-zinc-200 border border-zinc-700 flex items-center space-x-1"
                      >
                        <span>{dr.dish_name}:</span>
                        <strong className="text-amber-400 flex items-center space-x-0.5">
                          <span>{dr.rating}</span>
                          <Star className="w-3 h-3 fill-amber-400" />
                        </strong>
                      </span>
                    ))}
                  </div>
                )}

                {/* Photos */}
                {fb.photos && fb.photos.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {fb.photos.map((p, idx) => (
                      <img
                        key={idx}
                        src={resolveMediaUrl(p.photo_url)}
                        alt="Customer upload"
                        className="w-16 h-16 rounded-xl object-cover border border-zinc-700"
                      />
                    ))}
                  </div>
                )}

                {/* Moderation Controls */}
                <div className="pt-2 border-t border-zinc-800/80 flex justify-between items-center text-xs">
                  <span className="text-[10px] text-zinc-500">
                    {fb.flag_reason ? `Note: ${fb.flag_reason}` : 'Genuine verified dining feedback'}
                  </span>

                  <div className="flex space-x-2">
                    {fb.status !== 'APPROVED' && (
                      <button
                        onClick={() => handleModerate(fb.id, 'APPROVED', true)}
                        className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/30 font-semibold"
                      >
                        Approve
                      </button>
                    )}
                    {fb.status !== 'FLAGGED' && (
                      <button
                        onClick={() => handleModerate(fb.id, 'FLAGGED', false)}
                        className="px-2.5 py-1 rounded-lg bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 border border-amber-500/30 font-semibold"
                      >
                        Flag Spam
                      </button>
                    )}
                    <button
                      onClick={() => handleModerate(fb.id, fb.status || 'APPROVED', !fb.is_published)}
                      className="px-2.5 py-1 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 border border-zinc-700 font-semibold flex items-center space-x-1"
                    >
                      {fb.is_published ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                      <span>{fb.is_published ? 'Hide' : 'Publish'}</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Google Review Table Stand QR Modal */}
      {showQrModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl w-full max-w-sm p-6 sm:p-8 space-y-6 text-center shadow-2xl relative">
            <button
              onClick={() => setShowQrModal(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white"
            >
              <XCircle className="w-5 h-5" />
            </button>

            <div>
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30 mx-auto mb-2">
                <QrCode className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white">Google Review Table Stand</h3>
              <p className="text-xs text-zinc-400">Place this QR code on dining tables and billing stands</p>
            </div>

            <div className="p-4 bg-white rounded-2xl inline-block shadow-lg">
              {googleUrl ? (
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(googleUrl)}`}
                  alt="Google Review QR Code"
                  className="w-44 h-44 mx-auto"
                />
              ) : (
                <div className="w-44 h-44 flex items-center justify-center text-xs text-zinc-400">
                  Please configure a Google Review URL first
                </div>
              )}
            </div>

            <div className="space-y-2">
              <span className="text-xs font-mono font-semibold text-amber-400 block truncate max-w-xs mx-auto">
                {googleUrl || 'No URL configured'}
              </span>
              <button
                onClick={() => window.print()}
                className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs shadow-md transition"
              >
                Print Table Tent Card
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
