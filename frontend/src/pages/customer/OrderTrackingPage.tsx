import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Clock, ChefHat, CheckCircle2, AlertCircle, Bell,
  FileText, Flame, UtensilsCrossed, Sparkles, ArrowLeft,
  CheckCircle, Star, Camera, X, ExternalLink, ThumbsUp,
  MessageSquare, ShieldCheck, RefreshCw, Upload
} from 'lucide-react';
import { orderApi, feedbackApi, restaurantApi } from '../../services/api';
import { useWebSocket } from '../../context/WebSocketContext';
import { Order, OrderStatus } from '../../types';

export const OrderTrackingPage: React.FC = () => {
  const { orderId, qrToken } = useParams<{ orderId: string; qrToken: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Feedback State
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [googleReviewUrl, setGoogleReviewUrl] = useState<string | null>(null);

  // Ratings
  const [overallRating, setOverallRating] = useState(5);
  const [foodRating, setFoodRating] = useState(5);
  const [serviceRating, setServiceRating] = useState(5);
  const [ambienceRating, setAmbienceRating] = useState(5);
  const [cleanlinessRating, setCleanlinessRating] = useState(5);
  const [comment, setComment] = useState('');
  const [dishRatings, setDishRatings] = useState<Record<string, { rating: number; comment?: string }>>({});
  const [uploadedPhotos, setUploadedPhotos] = useState<string[]>([]);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);

  const { lastEvent, connectChannel } = useWebSocket();
  const basePath = qrToken ? `/table/${qrToken}` : '/menu';

  const orderStages: { status: OrderStatus; label: string; desc: string; icon: React.FC<{ className?: string }> }[] = [
    { status: 'PLACED', label: 'Order Placed', desc: 'Received by kitchen system', icon: FileText },
    { status: 'ACCEPTED', label: 'Order Accepted', desc: 'Queued at executive chef station', icon: CheckCircle },
    { status: 'PREPARING', label: 'Preparing', desc: 'Cooking with fresh ingredients', icon: Flame },
    { status: 'READY', label: 'Ready to Serve', desc: 'Plated & awaiting table runner', icon: UtensilsCrossed },
    { status: 'SERVED', label: 'Served', desc: 'Delivered to your table', icon: Sparkles },
    { status: 'COMPLETED', label: 'Completed', desc: 'Dining experience concluded', icon: CheckCircle2 },
  ];

  const fetchOrder = async () => {
    if (!orderId) return;
    try {
      const data = await orderApi.getById(parseInt(orderId, 10));
      setOrder(data);
      if (data.table_id) {
        connectChannel(`table/${data.table_id}`);
      }

      // Initialize dish ratings
      if (data.items && data.items.length > 0) {
        const initialDishMap: Record<string, { rating: number; comment?: string }> = {};
        data.items.forEach((item) => {
          initialDishMap[item.item_name] = { rating: 5, comment: '' };
        });
        setDishRatings(initialDishMap);
      }

      // Fetch restaurant Google review URL if available
      if (data.restaurant_id) {
        try {
          const restProfile = await restaurantApi.getProfile(data.restaurant_id);
          if (restProfile?.google_review_url) {
            setGoogleReviewUrl(restProfile.google_review_url);
          }
        } catch (e) {
          // ignore
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Order not found');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrder();
  }, [orderId]);

  // Handle incoming real-time WebSocket events
  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.type === 'ORDER_STATUS_CHANGED' &&
      lastEvent.data.order_id === parseInt(orderId || '0', 10)
    ) {
      fetchOrder();
    }
  }, [lastEvent, orderId]);

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      setFeedbackError('Photo size exceeds maximum 5MB limit.');
      return;
    }

    setUploadingPhoto(true);
    setFeedbackError(null);
    try {
      const res = await feedbackApi.uploadPhoto(file);
      if (res?.photo_url) {
        setUploadedPhotos((prev) => [...prev, res.photo_url]);
      }
    } catch (err: any) {
      setFeedbackError(err.response?.data?.detail || 'Failed to upload image. Please ensure valid PNG or JPEG.');
    } finally {
      setUploadingPhoto(false);
    }
  };

  const handleRemovePhoto = (idx: number) => {
    setUploadedPhotos((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!order) return;

    setSubmittingFeedback(true);
    setFeedbackError(null);

    const dishList = Object.entries(dishRatings).map(([name, val]) => ({
      dish_name: name,
      rating: val.rating,
      comment: val.comment || undefined,
    }));

    try {
      const res = await feedbackApi.submit({
        restaurant_id: order.restaurant_id,
        order_id: order.id,
        table_id: order.table_id,
        customer_name: order.customer_name || 'Dining Guest',
        customer_phone: order.customer_phone || undefined,
        overall_rating: overallRating,
        food_rating: foodRating,
        service_rating: serviceRating,
        ambience_rating: ambienceRating,
        cleanliness_rating: cleanlinessRating,
        comment: comment.trim() || undefined,
        dish_ratings: dishList,
        photo_urls: uploadedPhotos,
        allow_edit_if_exists: true,
      });

      if (res.google_review_url) {
        setGoogleReviewUrl(res.google_review_url);
      }
      setFeedbackSubmitted(true);
    } catch (err: any) {
      setFeedbackError(err.response?.data?.detail || 'Failed to submit review. Please try again.');
    } finally {
      setSubmittingFeedback(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center animate-fade-in pb-28">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Loading order tracker...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="p-8 text-center bg-[#12131a] rounded-3xl border border-zinc-800 max-w-md mx-auto my-12 pb-28">
        <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-2" />
        <h3 className="text-base font-bold text-white">Order Tracking Error</h3>
        <p className="text-xs text-zinc-400 mt-1">{error || 'Could not find this order.'}</p>
        <Link
          to={basePath}
          className="inline-block mt-4 px-4 py-2 rounded-xl bg-zinc-800 text-xs font-semibold text-zinc-200"
        >
          Return to Menu
        </Link>
      </div>
    );
  }

  const currentStageIndex = orderStages.findIndex((s) => s.status === order.status);
  const isOrderEligibleForRating =
    (order.status === 'SERVED' || order.status === 'COMPLETED') && order.payment_status === 'PAID';

  return (
    <div className="max-w-xl mx-auto space-y-5 animate-fade-in pb-32 sm:pb-16">
      <Link
        to={basePath}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Menu</span>
      </Link>

      {/* Main Status Header Card */}
      <div className="bg-gradient-to-br from-[#181924] to-[#12131a] border border-zinc-800 rounded-3xl p-5 sm:p-6 shadow-2xl relative overflow-hidden">
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className="text-[10px] font-bold text-brand-400 tracking-wider uppercase block">
              Live Order Tracker
            </span>
            <h2 className="text-xl font-black text-white mt-0.5">
              {order.order_number}
            </h2>
          </div>

          <div className="text-right">
            <span className="text-xs font-bold px-3 py-1 rounded-full bg-brand-500/15 text-brand-400 border border-brand-500/30">
              Table {order.table_number || order.table_id}
            </span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </div>

        {/* Dynamic Status Progress Bar */}
        <div className="mt-8 mb-8 px-2">
          <div className="relative flex items-center justify-between">
            <div className="absolute top-1/2 left-0 right-0 -translate-y-1/2 h-1 bg-zinc-800 -z-0"></div>
            <div
              className="absolute top-1/2 left-0 -translate-y-1/2 h-1 bg-gradient-to-r from-brand-600 to-amber-500 transition-all duration-500 -z-0"
              style={{
                width: `${Math.max(0, (currentStageIndex / (orderStages.length - 1)) * 100)}%`,
              }}
            ></div>

            {orderStages.map((stage, idx) => {
              const isPastOrCurrent = idx <= currentStageIndex;
              const isCurrent = idx === currentStageIndex;
              const StageIcon = stage.icon;

              return (
                <div key={stage.status} className="relative z-10 flex flex-col items-center">
                  <div
                    className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                      isCurrent
                        ? 'bg-brand-500 text-white ring-4 ring-brand-500/25 scale-110 shadow-lg shadow-brand-500/30'
                        : isPastOrCurrent
                        ? 'bg-amber-600 text-white'
                        : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
                    }`}
                  >
                    <StageIcon className="w-4 h-4" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Current Stage Label Highlight */}
          <div className="mt-5 p-3.5 rounded-2xl bg-zinc-900/90 border border-zinc-800 text-center">
            <span className="text-xs font-black text-brand-400 uppercase tracking-wide block">
              Current Stage: {orderStages[currentStageIndex]?.label || order.status}
            </span>
            <span className="text-xs text-zinc-300 mt-0.5 block">
              {orderStages[currentStageIndex]?.desc}
            </span>
          </div>
        </div>

        {/* Order Items Breakdown */}
        <div className="border-t border-zinc-800 pt-4">
          <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-3">
            Ordered Dishes ({order.items.length})
          </h4>
          <div className="space-y-2">
            {order.items.map((item) => (
              <div key={item.id} className="flex justify-between items-center text-xs">
                <div className="flex items-center space-x-2">
                  <span className="w-5 h-5 rounded-md bg-zinc-800 text-brand-400 font-extrabold flex items-center justify-center text-[10px]">
                    {item.quantity}×
                  </span>
                  <span className="font-medium text-zinc-200">{item.item_name}</span>
                </div>
                <span className="font-bold text-zinc-300">₹{item.total_price.toFixed(2)}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-zinc-800/80 flex justify-between items-center text-xs">
            <span className="text-zinc-400">Total Billed</span>
            <span className="text-base font-extrabold text-white">₹{order.total_amount.toFixed(2)}</span>
          </div>
        </div>

        {/* Customer Rating Callout (When Completed & Paid) */}
        {isOrderEligibleForRating && (
          <div className="mt-6 pt-5 border-t border-zinc-800">
            <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-transparent border border-amber-500/30 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center space-x-3 text-center sm:text-left">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30 flex-shrink-0">
                  <Star className="w-5 h-5 fill-amber-400" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">How was your meal today?</h4>
                  <p className="text-[11px] text-zinc-400">Rate your dishes and service to help us maintain culinary excellence.</p>
                </div>
              </div>
              <button
                onClick={() => setShowFeedbackModal(true)}
                className="w-full sm:w-auto px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold shadow-md shadow-amber-500/20 transition flex items-center justify-center space-x-1.5 flex-shrink-0"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{feedbackSubmitted ? 'Update Your Rating' : 'Rate Experience'}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Interactive Customer Feedback & Rating Modal */}
      {showFeedbackModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in overflow-y-auto">
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl w-full max-w-lg p-6 sm:p-8 space-y-6 shadow-2xl relative my-8 max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowFeedbackModal(false)}
              className="absolute top-5 right-5 p-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            {!feedbackSubmitted ? (
              <form onSubmit={handleSubmitFeedback} className="space-y-6">
                <div>
                  <div className="flex items-center space-x-2">
                    <div className="w-8 h-8 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
                      <Star className="w-4 h-4 fill-amber-400" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white">Rate Your Dining Experience</h3>
                      <p className="text-[11px] text-zinc-400">Order: {order.order_number} • Table {order.table_number || order.table_id}</p>
                    </div>
                  </div>
                </div>

                {feedbackError && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{feedbackError}</span>
                  </div>
                )}

                {/* Overall Rating */}
                <div className="p-4 rounded-2xl bg-zinc-900 border border-zinc-800 text-center space-y-2">
                  <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider block">
                    Overall Experience
                  </span>
                  <div className="flex justify-center space-x-2 pt-1">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <button
                        type="button"
                        key={s}
                        onClick={() => setOverallRating(s)}
                        className="p-1.5 transition transform hover:scale-125 focus:outline-none"
                      >
                        <Star
                          className={`w-7 h-7 ${
                            s <= overallRating
                              ? 'text-amber-400 fill-amber-400 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]'
                              : 'text-zinc-700'
                          }`}
                        />
                      </button>
                    ))}
                  </div>
                  <span className="text-xs font-semibold text-amber-400 block">
                    {overallRating === 5 && '🌟 Extraordinary Experience'}
                    {overallRating === 4 && '👍 Very Good'}
                    {overallRating === 3 && '👌 Satisfactory'}
                    {overallRating === 2 && '👎 Needs Improvement'}
                    {overallRating === 1 && '⚠️ Dissatisfied'}
                  </span>
                </div>

                {/* Multi-Attribute Ratings */}
                <div className="space-y-3 pt-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                    Experience Attributes
                  </span>

                  {/* Food Quality */}
                  <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
                    <span className="text-xs text-zinc-200 font-medium">Food Quality & Taste</span>
                    <div className="flex space-x-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <button
                          type="button"
                          key={s}
                          onClick={() => setFoodRating(s)}
                          className="focus:outline-none"
                        >
                          <Star className={`w-4 h-4 ${s <= foodRating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'}`} />
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Service Quality */}
                  <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
                    <span className="text-xs text-zinc-200 font-medium">Staff & Service Speed</span>
                    <div className="flex space-x-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <button
                          type="button"
                          key={s}
                          onClick={() => setServiceRating(s)}
                          className="focus:outline-none"
                        >
                          <Star className={`w-4 h-4 ${s <= serviceRating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'}`} />
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Cleanliness & Ambience */}
                  <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
                    <span className="text-xs text-zinc-200 font-medium">Cleanliness & Ambience</span>
                    <div className="flex space-x-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <button
                          type="button"
                          key={s}
                          onClick={() => {
                            setAmbienceRating(s);
                            setCleanlinessRating(s);
                          }}
                          className="focus:outline-none"
                        >
                          <Star className={`w-4 h-4 ${s <= ambienceRating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'}`} />
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Dish-level Ratings */}
                {order.items && order.items.length > 0 && (
                  <div className="space-y-2.5 pt-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                      Rate Your Ordered Dishes
                    </span>
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {order.items.map((item) => {
                        const currentDish = dishRatings[item.item_name] || { rating: 5, comment: '' };
                        return (
                          <div
                            key={item.id}
                            className="p-2.5 rounded-xl bg-zinc-900/80 border border-zinc-800 flex items-center justify-between gap-2"
                          >
                            <span className="text-xs font-medium text-white truncate max-w-[200px]">
                              {item.item_name}
                            </span>
                            <div className="flex space-x-1 flex-shrink-0">
                              {[1, 2, 3, 4, 5].map((s) => (
                                <button
                                  type="button"
                                  key={s}
                                  onClick={() =>
                                    setDishRatings((prev) => ({
                                      ...prev,
                                      [item.item_name]: { ...currentDish, rating: s },
                                    }))
                                  }
                                  className="focus:outline-none"
                                >
                                  <Star
                                    className={`w-3.5 h-3.5 ${
                                      s <= currentDish.rating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'
                                    }`}
                                  />
                                </button>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Optional Written Review */}
                <div className="space-y-1.5 pt-2">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                    Comments or Suggestions (Optional)
                  </label>
                  <textarea
                    rows={3}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Tell our chefs what you loved or how we can improve..."
                    className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-white placeholder-zinc-500 text-xs focus:outline-none focus:border-amber-500 resize-none"
                  />
                </div>

                {/* Optional Photo Upload */}
                <div className="space-y-2 pt-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                    Attach Photos (Optional)
                  </span>
                  <div className="flex flex-wrap gap-2 items-center">
                    {uploadedPhotos.map((pUrl, idx) => (
                      <div key={idx} className="relative w-16 h-16 rounded-xl border border-zinc-700 overflow-hidden group">
                        <img src={pUrl} alt="Dish photo" className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() => handleRemovePhoto(idx)}
                          className="absolute top-1 right-1 p-0.5 rounded-full bg-black/80 text-white hover:text-red-400"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                    {uploadedPhotos.length < 3 && (
                      <label className="w-16 h-16 rounded-xl border border-dashed border-zinc-700 hover:border-amber-500 bg-zinc-900/60 flex flex-col items-center justify-center cursor-pointer transition text-zinc-400 hover:text-white">
                        <Camera className="w-5 h-5 mb-1" />
                        <span className="text-[9px]">Add</span>
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          onChange={handlePhotoUpload}
                          disabled={uploadingPhoto}
                          className="hidden"
                        />
                      </label>
                    )}
                    {uploadingPhoto && <span className="text-xs text-amber-400 animate-pulse">Uploading...</span>}
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submittingFeedback}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-black font-extrabold text-xs shadow-lg shadow-amber-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
                >
                  {submittingFeedback ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Submitting Rating...</span>
                    </>
                  ) : (
                    <>
                      <ThumbsUp className="w-4 h-4" />
                      <span>Submit Verified Dining Rating</span>
                    </>
                  )}
                </button>
              </form>
            ) : (
              /* Post-Submission Screen with Optional Google Review Button */
              <div className="text-center space-y-6 py-4 animate-fade-in">
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/20">
                  <CheckCircle2 className="w-8 h-8" />
                </div>

                <div className="space-y-1">
                  <h3 className="text-xl font-bold text-white">Thank You for Your Review!</h3>
                  <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                    Your feedback helps our culinary and floor teams maintain the highest standards of hospitality.
                  </p>
                </div>

                {/* Google Review Prompt (Optional & Non-Automated) */}
                {googleReviewUrl && (
                  <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-3.5 text-left">
                    <div className="flex items-center space-x-2.5">
                      <div className="w-7 h-7 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center flex-shrink-0">
                        <ExternalLink className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-white block">Share Your Thoughts on Google</span>
                        <span className="text-[11px] text-zinc-400 block">Help others discover our dishes on Google Reviews</span>
                      </div>
                    </div>

                    <a
                      href={googleReviewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-md transition flex items-center justify-center space-x-2"
                    >
                      <span>Review Us on Google Maps</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>

                    <div className="p-2.5 rounded-lg bg-zinc-800/60 border border-zinc-700/60 text-[10px] text-zinc-400 flex items-start space-x-2">
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                      <span>
                        Google reviews are completely voluntary and submitted by you directly on Google. SRMP never posts reviews on your behalf, and positive ratings are not rewarded.
                      </span>
                    </div>
                  </div>
                )}

                <button
                  onClick={() => setShowFeedbackModal(false)}
                  className="px-6 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold border border-zinc-700"
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
