import { useState, useEffect } from "react";
import {
  Card,
  Row,
  Col,
  Statistic,
  Button,
  Space,
  Typography,
  Tag,
  List,
  message,
  Spin,
  Empty,
} from "antd";
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  DesktopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { useWebSocket } from "../contexts/WebSocketContext";
import { monitoringApi, deviceApi } from "../api";
import { Device, DeviceState } from "../types";

const { Title, Text } = Typography;

function DeviceStatusTag({ status }: { status: string }) {
  switch (status) {
    case "connected":
      return (
        <Tag icon={<CheckCircleOutlined />} color="success">
          Connected
        </Tag>
      );
    case "connecting":
      return (
        <Tag icon={<SyncOutlined spin />} color="processing">
          Connecting
        </Tag>
      );
    case "error":
      return (
        <Tag icon={<CloseCircleOutlined />} color="error">
          Error
        </Tag>
      );
    default:
      return <Tag color="default">Disconnected</Tag>;
  }
}

export default function DashboardPage() {
  const { status } = useWebSocket();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchDevices = async () => {
    try {
      const data = await deviceApi.list();
      setDevices(data);
    } catch (error) {
      console.error("Failed to fetch devices:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  // Merge device config with real-time status
  const devicesWithStatus = devices.map((device) => {
    const deviceStatus = status?.devices?.[device.screen_id] as
      | DeviceState
      | undefined;
    return {
      ...device,
      status: deviceStatus?.status || "disconnected",
      current_video: deviceStatus?.current_video,
      current_video_title: deviceStatus?.current_video_title,
      last_skip_time: deviceStatus?.last_skip_time,
      last_skip_category: deviceStatus?.last_skip_category,
      error_message: deviceStatus?.error_message,
    };
  });

  const handleStart = async () => {
    setActionLoading(true);
    try {
      await monitoringApi.start();
      message.success("Monitoring started");
    } catch (error) {
      message.error("Failed to start monitoring");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      await monitoringApi.stop();
      message.success("Monitoring stopped");
    } catch (error) {
      message.error("Failed to stop monitoring");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestart = async () => {
    setActionLoading(true);
    try {
      await monitoringApi.restart();
      message.success("Monitoring restarted");
    } catch (error) {
      message.error("Failed to restart monitoring");
    } finally {
      setActionLoading(false);
    }
  };

  const connectedCount = devicesWithStatus.filter(
    (d) => d.status === "connected",
  ).length;

  return (
    <div>
      <Row gutter={[16, 16]} align="middle" style={{ marginBottom: 24 }}>
        <Col flex="auto">
          <Title level={3} style={{ margin: 0 }}>
            Dashboard
          </Title>
        </Col>
        <Col>
          <Space>
            {status?.running ? (
              <>
                <Button
                  icon={<PauseCircleOutlined />}
                  onClick={handleStop}
                  loading={actionLoading}
                >
                  Stop
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleRestart}
                  loading={actionLoading}
                >
                  Restart
                </Button>
              </>
            ) : (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStart}
                loading={actionLoading}
                disabled={devices.length === 0}
              >
                Start Monitoring
              </Button>
            )}
          </Space>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Devices"
              value={devices.length}
              prefix={<DesktopOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Connected"
              value={connectedCount}
              valueStyle={{ color: connectedCount > 0 ? "#52c41a" : undefined }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Status"
              value={status?.running ? "Active" : "Stopped"}
              valueStyle={{ color: status?.running ? "#52c41a" : "#ff4d4f" }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="Devices"
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchDevices}>
            Refresh
          </Button>
        }
      >
        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : devices.length === 0 ? (
          <Empty
            description="No devices configured"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" href="/devices">
              Add Device
            </Button>
          </Empty>
        ) : (
          <List
            dataSource={devicesWithStatus}
            renderItem={(device) => (
              <List.Item
                extra={
                  <DeviceStatusTag status={device.status || "disconnected"} />
                }
              >
                <List.Item.Meta
                  avatar={<DesktopOutlined style={{ fontSize: 24 }} />}
                  title={device.name}
                  description={
                    <Space direction="vertical" size={0}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ID: {device.screen_id.substring(0, 20)}...
                      </Text>
                      {device.current_video_title && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Now Playing: {device.current_video_title}
                        </Text>
                      )}
                      {device.last_skip_category && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Last Skip: {device.last_skip_category}
                        </Text>
                      )}
                      {device.error_message && (
                        <Text type="danger" style={{ fontSize: 12 }}>
                          Error: {device.error_message}
                        </Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
