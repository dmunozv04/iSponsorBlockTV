import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Space, Typography, Badge } from "antd";
import {
  DashboardOutlined,
  DesktopOutlined,
  SettingOutlined,
  LogoutOutlined,
  WifiOutlined,
  DisconnectOutlined,
} from "@ant-design/icons";
import { useAuth } from "../contexts/AuthContext";
import { useWebSocket } from "../contexts/WebSocketContext";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, username } = useAuth();
  const { status, isConnected } = useWebSocket();

  const menuItems = [
    {
      key: "/",
      icon: <DashboardOutlined />,
      label: "Dashboard",
    },
    {
      key: "/devices",
      icon: <DesktopOutlined />,
      label: "Devices",
    },
    {
      key: "/settings",
      icon: <SettingOutlined />,
      label: "Settings",
    },
  ];

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        style={{
          overflow: "auto",
          height: "100vh",
          position: "fixed",
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <Text strong style={{ color: "#fff", fontSize: 16 }}>
            iSponsorBlockTV
          </Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout style={{ marginLeft: 200 }}>
        <Header
          style={{
            padding: "0 24px",
            background: "#141414",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <Space>
            <Badge
              status={status?.running ? "success" : "default"}
              text={
                <Text type={status?.running ? "success" : "secondary"}>
                  {status?.running ? "Monitoring Active" : "Monitoring Stopped"}
                </Text>
              }
            />
            <Text type="secondary">|</Text>
            {isConnected ? (
              <Badge
                status="success"
                text={
                  <Text type="success">
                    <WifiOutlined /> Connected
                  </Text>
                }
              />
            ) : (
              <Badge
                status="error"
                text={
                  <Text type="danger">
                    <DisconnectOutlined /> Disconnected
                  </Text>
                }
              />
            )}
          </Space>
          <Space>
            <Text type="secondary">Welcome, {username}</Text>
            <Button
              type="text"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
            >
              Logout
            </Button>
          </Space>
        </Header>
        <Content
          style={{
            margin: "24px",
            padding: 24,
            background: "#1f1f1f",
            borderRadius: 8,
            minHeight: "calc(100vh - 112px)",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
