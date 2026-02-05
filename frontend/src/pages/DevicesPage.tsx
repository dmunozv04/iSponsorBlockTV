import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Typography,
  Modal,
  Form,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Tag,
  Tabs,
  Spin,
  Empty,
  List,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  SearchOutlined,
  DesktopOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { deviceApi } from '../api'
import { Device } from '../types'
import { useWebSocket } from '../contexts/WebSocketContext'

const { Title, Text } = Typography

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [discoverModalOpen, setDiscoverModalOpen] = useState(false)
  const [editingDevice, setEditingDevice] = useState<Device | null>(null)
  const [discoveredDevices, setDiscoveredDevices] = useState<Device[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [pairing, setPairing] = useState(false)
  const [addForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [pairForm] = Form.useForm()
  const { status } = useWebSocket()

  const fetchDevices = async () => {
    try {
      const data = await deviceApi.list()
      setDevices(data)
    } catch (error) {
      message.error('Failed to fetch devices')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDevices()
  }, [])

  const handleDiscover = async () => {
    setDiscovering(true)
    try {
      const discovered = await deviceApi.discover()
      setDiscoveredDevices(discovered)
      if (discovered.length === 0) {
        message.info('No devices found on the network')
      }
    } catch (error) {
      message.error('Discovery failed. Make sure you\'re on the same network as your devices.')
    } finally {
      setDiscovering(false)
    }
  }

  const handlePair = async (values: { pairing_code: string }) => {
    setPairing(true)
    try {
      const device = await deviceApi.pair(values.pairing_code)
      // Add the paired device
      await deviceApi.add({
        screen_id: device.screen_id,
        name: device.name,
        offset: 0,
      })
      message.success(`Paired with ${device.name}`)
      pairForm.resetFields()
      setAddModalOpen(false)
      fetchDevices()
    } catch (error) {
      message.error('Pairing failed. Check the code and try again.')
    } finally {
      setPairing(false)
    }
  }

  const handleAddDiscovered = async (device: Device) => {
    try {
      await deviceApi.add({
        screen_id: device.screen_id,
        name: device.name,
        offset: device.offset || 0,
      })
      message.success(`Added ${device.name}`)
      setDiscoverModalOpen(false)
      fetchDevices()
    } catch (error) {
      message.error('Failed to add device')
    }
  }

  const handleAddManual = async (values: { screen_id: string; name: string; offset: number }) => {
    try {
      await deviceApi.add(values)
      message.success('Device added')
      addForm.resetFields()
      setAddModalOpen(false)
      fetchDevices()
    } catch (error) {
      message.error('Failed to add device')
    }
  }

  const handleEdit = (device: Device) => {
    setEditingDevice(device)
    editForm.setFieldsValue({
      screen_id: device.screen_id,
      name: device.name,
      offset: device.offset,
    })
    setEditModalOpen(true)
  }

  const handleEditSave = async (values: { screen_id: string; name: string; offset: number }) => {
    if (!editingDevice) return

    try {
      await deviceApi.update(editingDevice.screen_id, values)
      message.success('Device updated')
      setEditModalOpen(false)
      setEditingDevice(null)
      fetchDevices()
    } catch (error) {
      message.error('Failed to update device')
    }
  }

  const handleDelete = async (screenId: string) => {
    try {
      await deviceApi.remove(screenId)
      message.success('Device removed')
      fetchDevices()
    } catch (error) {
      message.error('Failed to remove device')
    }
  }

  const devicesWithStatus = devices.map((device) => ({
    ...device,
    status: status?.devices?.[device.screen_id]?.status || 'disconnected',
  }))

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Screen ID',
      dataIndex: 'screen_id',
      key: 'screen_id',
      render: (id: string) => (
        <Text copyable={{ text: id }} style={{ fontSize: 12 }}>
          {id.substring(0, 30)}...
        </Text>
      ),
    },
    {
      title: 'Offset (ms)',
      dataIndex: 'offset',
      key: 'offset',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => {
        switch (s) {
          case 'connected':
            return <Tag color="success">Connected</Tag>
          case 'connecting':
            return <Tag color="processing">Connecting</Tag>
          case 'error':
            return <Tag color="error">Error</Tag>
          default:
            return <Tag>Disconnected</Tag>
        }
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: Device) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="Remove device?"
            description="This will remove the device from monitoring."
            onConfirm={() => handleDelete(record.screen_id)}
            okText="Yes"
            cancelText="No"
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={3}>Devices</Title>

      <Card
        extra={
          <Space>
            <Button
              icon={<SearchOutlined />}
              onClick={() => {
                setDiscoverModalOpen(true)
                handleDiscover()
              }}
            >
              Discover
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setAddModalOpen(true)}
            >
              Add Device
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={devicesWithStatus}
          columns={columns}
          rowKey="screen_id"
          loading={loading}
          locale={{
            emptyText: (
              <Empty
                description="No devices configured"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
        />
      </Card>

      {/* Add Device Modal */}
      <Modal
        title="Add Device"
        open={addModalOpen}
        onCancel={() => {
          setAddModalOpen(false)
          addForm.resetFields()
          pairForm.resetFields()
        }}
        footer={null}
        width={500}
      >
        <Tabs
          items={[
            {
              key: 'pair',
              label: 'Pair with Code',
              children: (
                <Form form={pairForm} onFinish={handlePair} layout="vertical">
                  <Form.Item
                    label="Pairing Code"
                    name="pairing_code"
                    help="Find this in YouTube TV app: Settings → Link with TV code"
                    rules={[{ required: true, message: 'Enter the pairing code' }]}
                  >
                    <Input
                      placeholder="XXXX-XXXX-XXXX"
                      size="large"
                      style={{ letterSpacing: 2 }}
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" loading={pairing} block>
                      Pair Device
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'manual',
              label: 'Add Manually',
              children: (
                <Form
                  form={addForm}
                  onFinish={handleAddManual}
                  layout="vertical"
                  initialValues={{ offset: 0 }}
                >
                  <Form.Item
                    label="Screen ID"
                    name="screen_id"
                    rules={[{ required: true, message: 'Enter the screen ID' }]}
                  >
                    <Input placeholder="Screen ID from YouTube TV" />
                  </Form.Item>
                  <Form.Item
                    label="Name"
                    name="name"
                    rules={[{ required: true, message: 'Enter a name' }]}
                  >
                    <Input placeholder="Living Room TV" />
                  </Form.Item>
                  <Form.Item
                    label="Offset (ms)"
                    name="offset"
                    help="Time offset for skip timing (usually 0)"
                  >
                    <InputNumber style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block>
                      Add Device
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Modal>

      {/* Edit Device Modal */}
      <Modal
        title="Edit Device"
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false)
          setEditingDevice(null)
        }}
        footer={null}
      >
        <Form form={editForm} onFinish={handleEditSave} layout="vertical">
          <Form.Item label="Screen ID" name="screen_id">
            <Input disabled />
          </Form.Item>
          <Form.Item
            label="Name"
            name="name"
            rules={[{ required: true, message: 'Enter a name' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="Offset (ms)" name="offset">
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Save Changes
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Discover Devices Modal */}
      <Modal
        title="Discover Devices"
        open={discoverModalOpen}
        onCancel={() => setDiscoverModalOpen(false)}
        footer={
          <Button icon={<ReloadOutlined />} onClick={handleDiscover} loading={discovering}>
            Refresh
          </Button>
        }
      >
        {discovering ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">Searching for devices...</Text>
            </div>
          </div>
        ) : discoveredDevices.length === 0 ? (
          <Empty
            description="No devices found"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Text type="secondary">
              Make sure your devices are on the same network and have YouTube TV open.
            </Text>
          </Empty>
        ) : (
          <List
            dataSource={discoveredDevices}
            renderItem={(device) => {
              const alreadyAdded = devices.some((d) => d.screen_id === device.screen_id)
              return (
                <List.Item
                  actions={[
                    alreadyAdded ? (
                      <Tag color="success">Added</Tag>
                    ) : (
                      <Button
                        type="primary"
                        size="small"
                        onClick={() => handleAddDiscovered(device)}
                      >
                        Add
                      </Button>
                    ),
                  ]}
                >
                  <List.Item.Meta
                    avatar={<DesktopOutlined style={{ fontSize: 24 }} />}
                    title={device.name}
                    description={
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {device.screen_id.substring(0, 40)}...
                      </Text>
                    }
                  />
                </List.Item>
              )
            }}
          />
        )}
      </Modal>
    </div>
  )
}
