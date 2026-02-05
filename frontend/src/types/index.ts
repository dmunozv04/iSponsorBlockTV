// API types

export interface Device {
  screen_id: string;
  name: string;
  offset: number;
  status?: "disconnected" | "connecting" | "connected" | "error";
  current_video?: string;
  current_video_title?: string;
  error_message?: string;
  last_skip_time?: string;
  last_skip_category?: string;
}

export interface ChannelWhitelist {
  id: string;
  name: string;
}

export interface Config {
  devices: Device[];
  skip_categories: string[];
  skip_count_tracking: boolean;
  mute_ads: boolean;
  skip_ads: boolean;
  minimum_skip_length: number;
  auto_play: boolean;
  join_name: string;
  apikey: string;
  channel_whitelist: ChannelWhitelist[];
  use_proxy: boolean;
}

export interface Category {
  value: string;
  label: string;
}

export interface ChannelSearchResult {
  id: string;
  name: string;
  subscribers: string;
}

export interface MonitoringStatus {
  running: boolean;
  device_count: number;
  devices: Record<string, DeviceState>;
}

export interface DeviceState {
  screen_id: string;
  name: string;
  status: "disconnected" | "connecting" | "connected" | "error";
  current_video?: string;
  current_video_title?: string;
  last_skip_time?: string;
  last_skip_category?: string;
  error_message?: string;
}

// WebSocket message types
export interface WSMessage {
  type: string;
  data?: unknown;
  screen_id?: string;
}

export interface WSDeviceStatusMessage extends WSMessage {
  type: "device_status";
  screen_id: string;
  data: DeviceState;
}

export interface WSInitialStatusMessage extends WSMessage {
  type: "initial_status";
  data: MonitoringStatus;
}
