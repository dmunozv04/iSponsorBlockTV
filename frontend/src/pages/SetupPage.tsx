import { useState } from "react";
import { Card, Form, Input, Button, Typography, message, Space } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useAuth } from "../contexts/AuthContext";

const { Title, Text } = Typography;

export default function SetupPage() {
  const [loading, setLoading] = useState(false);
  const { setupAuth } = useAuth();

  const onFinish = async (values: {
    username: string;
    password: string;
    confirmPassword: string;
  }) => {
    if (values.password !== values.confirmPassword) {
      message.error("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      const success = await setupAuth(values.username, values.password);
      if (success) {
        message.success("Setup complete!");
      } else {
        message.error("Setup failed. Please try again.");
      }
    } catch {
      message.error("Setup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#141414",
      }}
    >
      <Card style={{ width: 400, background: "#1f1f1f" }} bordered={false}>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <div style={{ textAlign: "center" }}>
            <Title level={2} style={{ marginBottom: 8 }}>
              iSponsorBlockTV
            </Title>
            <Text type="secondary">
              Welcome! Set up your admin credentials to get started.
            </Text>
          </div>

          <Form
            name="setup"
            onFinish={onFinish}
            layout="vertical"
            requiredMark={false}
          >
            <Form.Item
              name="username"
              rules={[
                { required: true, message: "Please enter a username" },
                { min: 3, message: "Username must be at least 3 characters" },
              ]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="Username"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: "Please enter a password" },
                { min: 8, message: "Password must be at least 8 characters" },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Password"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="confirmPassword"
              rules={[
                { required: true, message: "Please confirm your password" },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="Confirm Password"
                size="large"
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                size="large"
                block
                loading={loading}
              >
                Create Account
              </Button>
            </Form.Item>
          </Form>
        </Space>
      </Card>
    </div>
  );
}
