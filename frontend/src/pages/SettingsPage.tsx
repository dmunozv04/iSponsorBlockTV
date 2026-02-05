import { useState, useEffect } from 'react'
import {
  Card,
  Form,
  Switch,
  InputNumber,
  Input,
  Button,
  Typography,
  message,
  Checkbox,
  Space,
  Divider,
  Table,
  Modal,
  List,
  Spin,
  Tag,
  Popconfirm,
  Row,
  Col,
} from 'antd'
import {
  SaveOutlined,
  PlusOutlined,
  DeleteOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { configApi, channelApi } from '../api'
import { Config, Category, ChannelWhitelist, ChannelSearchResult } from '../types'

const { Title, Text } = Typography

export default function SettingsPage() {
  const [config, setConfig] = useState<Config | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [channelModalOpen, setChannelModalOpen] = useState(false)
  const [channelSearchResults, setChannelSearchResults] = useState<ChannelSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [form] = Form.useForm()

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [configData, categoriesData] = await Promise.all([
          configApi.get(),
          configApi.getCategories(),
        ])
        setConfig(configData)
        setCategories(categoriesData)
        form.setFieldsValue({
          skip_categories: configData.skip_categories,
          skip_count_tracking: configData.skip_count_tracking,
          mute_ads: configData.mute_ads,
          skip_ads: configData.skip_ads,
          minimum_skip_length: configData.minimum_skip_length,
          auto_play: configData.auto_play,
          join_name: configData.join_name,
          apikey: configData.apikey,
          use_proxy: configData.use_proxy,
        })
      } catch (error) {
        message.error('Failed to load settings')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [form])

  const handleSave = async (values: Partial<Config>) => {
    setSaving(true)
    try {
      // Include whitelist from config state
      await configApi.update({
        ...values,
        channel_whitelist: config?.channel_whitelist,
      })
      message.success('Settings saved')
      // Refresh config
      const newConfig = await configApi.get()
      setConfig(newConfig)
    } catch (error) {
      message.error('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleSearchChannels = async () => {
    if (!searchQuery.trim()) return

    setSearching(true)
    try {
      const results = await channelApi.search(searchQuery)
      setChannelSearchResults(results)
    } catch (error) {
      message.error('Channel search failed. Make sure you have a YouTube API key configured.')
    } finally {
      setSearching(false)
    }
  }

  const handleAddChannel = async (channel: ChannelSearchResult) => {
    if (!config) return

    const newWhitelist = [
      ...config.channel_whitelist,
      { id: channel.id, name: channel.name },
    ]

    try {
      await configApi.update({ channel_whitelist: newWhitelist })
      setConfig({ ...config, channel_whitelist: newWhitelist })
      message.success(`Added ${channel.name} to whitelist`)
    } catch (error) {
      message.error('Failed to add channel')
    }
  }

  const handleRemoveChannel = async (channelId: string) => {
    if (!config) return

    const newWhitelist = config.channel_whitelist.filter((c) => c.id !== channelId)

    try {
      await configApi.update({ channel_whitelist: newWhitelist })
      setConfig({ ...config, channel_whitelist: newWhitelist })
      message.success('Channel removed from whitelist')
    } catch (error) {
      message.error('Failed to remove channel')
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Spin size="large" />
      </div>
    )
  }

  const whitelistColumns = [
    {
      title: 'Channel Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Channel ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => (
        <Text copyable type="secondary" style={{ fontSize: 12 }}>
          {id}
        </Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: ChannelWhitelist) => (
        <Popconfirm
          title="Remove channel from whitelist?"
          onConfirm={() => handleRemoveChannel(record.id)}
          okText="Yes"
          cancelText="No"
        >
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <Title level={3}>Settings</Title>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          skip_count_tracking: true,
          mute_ads: false,
          skip_ads: false,
          minimum_skip_length: 1,
          auto_play: true,
          use_proxy: false,
        }}
      >
        <Row gutter={24}>
          <Col xs={24} lg={12}>
            <Card title="Skip Categories" style={{ marginBottom: 24 }}>
              <Form.Item
                name="skip_categories"
                help="Select which types of segments to automatically skip"
              >
                <Checkbox.Group>
                  <Row>
                    {categories.map((cat) => (
                      <Col span={12} key={cat.value}>
                        <Checkbox value={cat.value} style={{ marginBottom: 8 }}>
                          {cat.label}
                        </Checkbox>
                      </Col>
                    ))}
                  </Row>
                </Checkbox.Group>
              </Form.Item>

              <Divider />

              <Form.Item
                label="Minimum Skip Length (seconds)"
                name="minimum_skip_length"
                help="Skip only segments longer than this duration"
              >
                <InputNumber min={0} max={60} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name="skip_count_tracking"
                valuePropName="checked"
                help="Report skipped segments to SponsorBlock (anonymous)"
              >
                <Switch /> <Text style={{ marginLeft: 8 }}>Report skipped segments</Text>
              </Form.Item>
            </Card>

            <Card title="Ad Handling" style={{ marginBottom: 24 }}>
              <Form.Item
                name="mute_ads"
                valuePropName="checked"
                help="Automatically mute YouTube ads"
              >
                <Switch /> <Text style={{ marginLeft: 8 }}>Mute Ads</Text>
              </Form.Item>

              <Form.Item
                name="skip_ads"
                valuePropName="checked"
                help="Automatically click 'Skip Ad' button when available"
              >
                <Switch /> <Text style={{ marginLeft: 8 }}>Skip Ads</Text>
              </Form.Item>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card title="General Settings" style={{ marginBottom: 24 }}>
              <Form.Item
                label="Display Name"
                name="join_name"
                help="Name shown when connecting to devices"
              >
                <Input placeholder="iSponsorBlockTV" />
              </Form.Item>

              <Form.Item
                name="auto_play"
                valuePropName="checked"
                help="Enable YouTube autoplay on devices"
              >
                <Switch /> <Text style={{ marginLeft: 8 }}>Enable Autoplay</Text>
              </Form.Item>

              <Form.Item
                name="use_proxy"
                valuePropName="checked"
                help="Use system proxy for network requests"
              >
                <Switch /> <Text style={{ marginLeft: 8 }}>Use System Proxy</Text>
              </Form.Item>
            </Card>

            <Card title="YouTube API" style={{ marginBottom: 24 }}>
              <Form.Item
                label="API Key"
                name="apikey"
                help="Required for channel whitelist search functionality"
              >
                <Input.Password placeholder="YouTube Data API v3 key" />
              </Form.Item>
            </Card>
          </Col>
        </Row>

        <Card
          title="Channel Whitelist"
          style={{ marginBottom: 24 }}
          extra={
            <Button
              icon={<PlusOutlined />}
              onClick={() => setChannelModalOpen(true)}
              disabled={!form.getFieldValue('apikey')}
            >
              Add Channel
            </Button>
          }
        >
          <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            Channels on this list will not have their segments skipped.
          </Text>
          <Table
            dataSource={config?.channel_whitelist.filter((c) => c.id) || []}
            columns={whitelistColumns}
            rowKey="id"
            size="small"
            pagination={false}
            locale={{
              emptyText: 'No channels whitelisted',
            }}
          />
        </Card>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            icon={<SaveOutlined />}
            loading={saving}
            size="large"
          >
            Save Settings
          </Button>
        </Form.Item>
      </Form>

      {/* Channel Search Modal */}
      <Modal
        title="Add Channel to Whitelist"
        open={channelModalOpen}
        onCancel={() => {
          setChannelModalOpen(false)
          setChannelSearchResults([])
          setSearchQuery('')
        }}
        footer={null}
        width={600}
      >
        <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
          <Input
            placeholder="Search for a channel..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onPressEnter={handleSearchChannels}
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearchChannels}
            loading={searching}
          >
            Search
          </Button>
        </Space.Compact>

        {searching ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : (
          <List
            dataSource={channelSearchResults}
            locale={{ emptyText: 'Search for channels to add to whitelist' }}
            renderItem={(channel) => {
              const alreadyAdded = config?.channel_whitelist.some((c) => c.id === channel.id)
              return (
                <List.Item
                  actions={[
                    alreadyAdded ? (
                      <Tag color="success">Added</Tag>
                    ) : (
                      <Button
                        type="primary"
                        size="small"
                        onClick={() => handleAddChannel(channel)}
                      >
                        Add
                      </Button>
                    ),
                  ]}
                >
                  <List.Item.Meta
                    title={channel.name}
                    description={`${channel.subscribers} subscribers`}
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
