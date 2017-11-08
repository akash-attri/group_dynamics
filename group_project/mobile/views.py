from datetime import datetime, time, date
import networkx as nx
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon

from rest_framework import serializers, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from .models import UserProfile, LocationDensity, GroupLocalization, DailyMatrix, Groups
from .constants import GEOFENCE_BOUNDS, UNKNOWN_GEOFENCE, GEOFENCE_NAMES


class UserListSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'first_name', 'last_name')


class UserProfileSerializer(ModelSerializer):
    user = UserListSerializer()

    class Meta:
        model = UserProfile
        fields = ('user', 'gender', 'imei', 'bt_name')

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        base_user = User.objects.create_user(**user_data)
        account = UserProfile.objects.get_or_create(user=base_user, **validated_data)[0]
        return account


class UserCreateAPIView(CreateAPIView):
    permission_classes = [AllowAny]
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class UserLoginSerializer(ModelSerializer):

    password = serializers.CharField(
        required=False, style={'input_type': 'password'}
    )

    default_error_messages = {
        'invalid_credentials': 'Unable to login with provided credentials.',
        'inactive_account': 'User account is disabled.',
    }

    def __init__(self, *args, **kwargs):
        super(UserLoginSerializer, self).__init__(*args, **kwargs)
        self.user = None
        self.fields[User.USERNAME_FIELD] = serializers.CharField(
            required=False
        )

    def validate(self, data):
        self.user = authenticate(
            username=data.get('username'),
            password=data.get('password')
        )
        self._validate_user_exists(self.user)
        self._validate_user_is_active(self.user)
        return data

    def _validate_user_exists(self, user):
        if not user:
            self.fail('invalid_credentials')

    def _validate_user_is_active(self, user):
        if not user.is_active:
            self.fail('inactive_account')

    class Meta:
        model = User
        fields = ('username', 'password')


class UserLoginAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def post(self, request, *args, **kwargs):
        data = request.data
        serializer = UserLoginSerializer(data=data)
        if serializer.is_valid(raise_exception=True):
            user = User.objects.get(username=serializer.data.get('username'))
            user_data = {'user_id': user.id}
            return Response(user_data, status=HTTP_200_OK)
        return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)


class LocationDensitySerializer(ModelSerializer):
    geofence = serializers.SerializerMethodField('geofencename')

    def geofencename(self, obj):
        return GEOFENCE_NAMES[obj.location]

    class Meta:
        model = LocationDensity
        fields = '__all__'


@api_view(['POST'])
@permission_classes((permissions.AllowAny,))
def assign_groups(request):
    json = request.data
    if request.method == 'POST':
        username = list(json.keys())[0]
        data = list(json.values())[0]
        for entry in data:
            user = User.objects.get(username=username)
            time = entry['time'].split(':')[0] + ':' + entry['time'].split(':')[1]
            timestamp = datetime.combine(
                datetime.strptime(entry['date'], '%d/%m/%Y').date(),
                datetime.strptime(time, '%H:%M').time()
            )
            GroupLocalization.objects.create(
                user=UserProfile.objects.get(user=user),
                timestamp=timestamp,
                group=str(entry['group'])
            )
            location = assign_geofence(entry['location']['lat'], entry['location']['long'])
            if LocationDensity.objects.filter(timestamp=timestamp, location=location).exists():
                loc_obj = LocationDensity.objects.get(timestamp=timestamp, location=location)
                loc_obj.density += 1
                loc_obj.save()
            else:
                LocationDensity.objects.create(timestamp=timestamp, location=location, density=1)
        return Response({"message": "Got some data!", "data": request.data})
    return Response({"message": "Data format inaccurate !!!!!"})


def assign_geofence(lat, long):
    coordinates = Point(float(lat), float(long))
    for area in GEOFENCE_BOUNDS:
        points_list = [(point['lat'], point['long']) for point in GEOFENCE_BOUNDS[area]]
        points_list.append(points_list[0])
        polygon = Polygon(points_list)
        if polygon.contains(coordinates):
            return area
    return UNKNOWN_GEOFENCE


@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def density_api(request):
    location_density = LocationDensity.objects.filter(
        timestamp__range=(datetime.combine(date(2017, 11, 6), time.min),
                          datetime.combine(datetime.now().date(), time.max))
    )
    serializer = LocationDensitySerializer(location_density, many=True)
    loc_density = {}
    data = []
    for loc_obj in serializer.data:
        loc_density[loc_obj['geofence']] = loc_density.get(loc_obj['geofence'], 0) + loc_obj['density']
    for locn in list(loc_density.keys()):
        data.append({
            'name': locn,
            'strength': loc_density[locn]
        })
    return Response({'data': data}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def strength_api(request, uid):
    user = UserProfile.objects.get(user_id=uid)
    group = identify_group(user)
    data = []
    for friend in list(group.keys()):
        data.append({
            'username': friend,
            'strength': group[friend]
        })
    return Response({'data': data}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def gender_api(request):
    data = [
        {'name': 'girls', 'value': Groups.objects.filter(dynamic='Girls').count()},
        {'name': 'boys', 'value': Groups.objects.filter(dynamic='Boys').count()},
        {'name': 'mixed', 'value': Groups.objects.filter(dynamic='Both').count()}
    ]
    return Response({'data': data}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def groups_api(request, uid):
    data = []
    for group in Groups.objects.all():
        members = []
        user_strength = 0
        grp = eval(group.members)
        if int(uid) in grp:
            for frnd in grp:
                matrix = eval(DailyMatrix.objects.first().group)
                try:
                    strength = matrix[User.objects.get(id=uid).username][User.objects.get(id=frnd).username]
                except:
                    try:
                        strength = matrix[User.objects.get(id=frnd).username][User.objects.get(id=uid).username]
                    except:
                        strength = 0
                members.append({
                    'name': User.objects.get(id=frnd).username,
                    'strength': strength
                })
                user_strength += strength
            data.append({
                'group_id': group.id,
                'group_strength': user_strength,
                'members': members
            })
    return Response({'data': data}, status=HTTP_200_OK)


def data_analysis():
    timestamp_set = {}
    users = UserProfile.objects.all()
    for usr in users:
        timestamp_set[usr.user.username] = identify_group(usr)
    DailyMatrix.objects.all().delete()
    DailyMatrix.objects.create(date=datetime.now().date(), group=str(timestamp_set))


def identify_group(user):
    dict = {}
    group_objects = GroupLocalization.objects.filter(user=user).order_by('timestamp')
    for group_obj in group_objects:
        group_dict = eval(group_obj.group)
        for friend in list(group_dict.keys()):
            grp_strength = dict.get(friend, 0) + group_dict[friend]
            dict[friend] = grp_strength
    return dict


def make_graph():
    user_node = {}
    for usr in UserProfile.objects.all():
        user_node[usr.user.username] = usr.user.id
    graph = nx.Graph()
    matrix_obj = DailyMatrix.objects.first()
    matrix = eval(matrix_obj.group)
    for usr in list(matrix.keys()):
        for friend in list(matrix[usr].keys()):
            if not user_node.get(usr) or not user_node.get(friend):
                continue
            graph.add_edge(user_node[usr], user_node[friend], weight=matrix[usr][friend])

    threshold_graph(graph, 'Weak', 10, 30)
    threshold_graph(graph, 'Neutral', 31, 50)
    threshold_graph(graph, 'Strong', 51)


def threshold_graph(graph, gp_type, min_wt, max_wt=1000):
    grp_graph = nx.Graph([(u, v, d) for (u, v, d) in graph.edges(data=True) if min_wt <= d['weight'] <= max_wt])
    groups_list = list(nx.find_cliques(grp_graph))
    for grp in groups_list:
        group = Groups.objects.create(members=str(grp), type=gp_type)
        ml = fml = False
        for uid in grp:
            ml = True if UserProfile.objects.get(user_id=uid).gender in ['male', 'Male'] else ml
            fml = True if UserProfile.objects.get(user_id=uid).gender in ['female', 'Female'] else fml
        if ml and fml:
            group.dynamic = 'Both'
        elif ml:
            group.dynamic = 'Boys'
        else:
            group.dynamic = 'Girls'
        group.save()
